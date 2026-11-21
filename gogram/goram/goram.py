#!/usr/bin/env python3
"""GORAM development ledger. Internal API only; not cryptocurrency or public wallet."""
import hmac
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("GORAM_DB", "goram.sqlite3")
TOKEN = os.environ.get("GORAM_INTERNAL_TOKEN", "")
PORT = int(os.environ.get("GORAM_PORT", "2840"))
UNIT = 1_000_000  # 1 GORAM = 1,000,000 microGORAM
IDENT = re.compile(r"^[0-9]{1,20}$")
MAX_AMOUNT = 10**18

def connect():
    db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("""CREATE TABLE IF NOT EXISTS wallets (
        user_id TEXT PRIMARY KEY,
        balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0))""")
    db.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
        sender TEXT, recipient TEXT NOT NULL, amount INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    return db

def parse_user(val):
    if not isinstance(val, str) or not IDENT.fullmatch(val):
        raise ValueError("user_id must be a decimal GoGram user ID string")
    return val

def parse_amount(val):
    if type(val) is not int or not 1 <= val <= MAX_AMOUNT:
        raise ValueError("amount must be a positive integer in microGORAM")
    return val

def balance(db, user):
    parse_user(user)
    db.execute("INSERT OR IGNORE INTO wallets(user_id) VALUES (?)", (user,))
    return db.execute("SELECT balance FROM wallets WHERE user_id=?", (user,)).fetchone()[0]

def move(db, sender, recipient, amount, request_id, allow_mint=False):
    recipient = parse_user(recipient)
    if sender is not None:
        sender = parse_user(sender)
    if sender is None and not allow_mint:
        raise ValueError("minting not permitted")
    amount = parse_amount(amount)
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise ValueError("request_id required (1-128 characters)")
    if sender == recipient:
        raise ValueError("self-transfer is not permitted")
    db.execute("BEGIN IMMEDIATE")
    try:
        existing = db.execute("SELECT id, sender, recipient, amount FROM transactions WHERE request_id=?", (request_id,)).fetchone()
        if existing:
            if (existing[1], existing[2], existing[3]) != (sender, recipient, amount):
                raise ValueError("request_id already used with different parameters")
            db.execute("COMMIT")
            return {"tx_id": existing[0], "duplicate": True}
        if sender is not None:
            balance(db, sender)
            cursor = db.execute("UPDATE wallets SET balance=balance-? WHERE user_id=? AND balance>=?", (amount, sender, amount))
            if cursor.rowcount != 1:
                raise ValueError("insufficient funds")
        balance(db, recipient)
        current = db.execute("SELECT balance FROM wallets WHERE user_id=?", (recipient,)).fetchone()[0]
        if current + amount > 2**63 - 1:
            raise ValueError("recipient balance overflow")
        db.execute("UPDATE wallets SET balance=balance+? WHERE user_id=?", (amount, recipient))
        txid = str(uuid.uuid4())
        db.execute("INSERT INTO transactions(id,request_id,sender,recipient,amount) VALUES(?,?,?,?,?)",
                   (txid, request_id, sender, recipient, amount))
        db.execute("COMMIT")
        return {"tx_id": txid, "duplicate": False}
    except Exception:
        db.execute("ROLLBACK")
        raise

class API(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        auth = self.headers.get("Authorization", "")
        return bool(TOKEN) and hmac.compare_digest(auth, "Bearer " + TOKEN)

    def do_GET(self):
        if not self.authorized():
            return self.reply(401, {"error": "unauthorized"})
        if self.path == "/health":
            return self.reply(200, {"service": "GORAM", "network": "internal-dev", "unit": UNIT})
        if self.path.startswith("/balance/"):
            try:
                user = parse_user(self.path.removeprefix("/balance/"))
                with closing(connect()) as db:
                    amount = balance(db, user)
                return self.reply(200, {"user_id": user, "microgoram": amount})
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {"error": "unauthorized"})
        if self.path not in ("/internal/mint", "/internal/transfer"):
            return self.reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError("invalid payload length")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("expected JSON object")
            with closing(connect()) as db:
                result = move(db, None if self.path.endswith("/mint") else data.get("from"),
                    data.get("to"), data.get("amount"), data.get("request_id"),
                    allow_mint=self.path.endswith("/mint"))
            self.reply(200, result)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})
        except sqlite3.Error:
            self.reply(500, {"error": "database operation failed"})

if __name__ == "__main__":
    if len(TOKEN) < 32:
        raise SystemExit("Set a random GORAM_INTERNAL_TOKEN (minimum 32 chars)")
    with closing(connect()):
        pass
    print(f"GORAM internal development service on 127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), API).serve_forever()
