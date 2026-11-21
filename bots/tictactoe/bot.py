#!/usr/bin/env python3
"""GoGram Tic-Tac-Toe via OwpenGram Bot API. No external Python packages."""
import getpass
import json
import logging
import os
import random
import secrets
import signal
import sqlite3
import sys
import time
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = os.getenv("GOGRAM_BOT_API_URL", "http://127.0.0.1:2500").rstrip("/")
TOKEN = os.getenv("GOGRAM_BOT_TOKEN", "")
DB = os.getenv("GOGRAM_TT_DB", "tt.sqlite3")
LOG = logging.getLogger("gogram-tt")
RUN = True
WIN_LINES = ((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
EMPTY = "·"

def api(method, params):
    data = json.dumps(params, ensure_ascii=False).encode("utf-8")
    req = Request(f"{BASE}/bot{TOKEN}/{method}", data=data,
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=55 if method == "getUpdates" else 12) as res:
            payload = json.load(res)
    except HTTPError as exc:
        body = exc.read(1200).decode("utf-8", "replace")
        raise RuntimeError(f"{method}: HTTP {exc.code}: {body}") from exc
    if not payload.get("ok"):
        raise RuntimeError(f"{method}: {payload.get('description', payload)}")
    return payload.get("result")

def db_conn():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS games("
               "id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL DEFAULT 0,"
               "x_id INTEGER NOT NULL, o_id INTEGER NOT NULL DEFAULT 0,"
               "board TEXT NOT NULL DEFAULT '---------', turn TEXT NOT NULL DEFAULT 'X',"
               "status TEXT NOT NULL DEFAULT 'waiting', private_ai INTEGER NOT NULL DEFAULT 0,"
               "created_at INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.commit()
    return db

def winner(board):
    for a, b, c in WIN_LINES:
        if board[a] != "-" and board[a] == board[b] == board[c]:
            return board[a]
    return "draw" if "-" not in board else None

def keyboard(game):
    gid = game["id"]
    if game["status"] == "waiting":
        return {"inline_keyboard": [[{"text":"➕ присоединиться (O)", "callback_data":f"tt:{gid}:join"}],
                                   [{"text":"✖ отменить", "callback_data":f"tt:{gid}:cancel"}]]}
    if game["status"] in ("done", "cancelled"):
        return {"inline_keyboard": [[{"text":"🔄 новая игра", "callback_data":f"tt:{gid}:again"}]]}
    cells = []
    for row in range(3):
        buttons = []
        for col in range(3):
            ix = row*3+col
            mark = game["board"][ix]
            buttons.append({"text": "❌" if mark == "X" else "⭕" if mark == "O" else "⬜",
                            "callback_data":f"tt:{gid}:m{ix}"})
        cells.append(buttons)
    cells.append([{"text":"✖ завершить", "callback_data":f"tt:{gid}:cancel"}])
    return {"inline_keyboard":cells}

def display(game):
    rows = [game["board"][i:i+3] for i in (0,3,6)]
    graphic = "\n".join(" ".join("❌" if c=="X" else "⭕" if c=="O" else "▫️" for c in row) for row in rows)
    title = "🎮 крестики-нолики"
    if game["status"] == "waiting":
        status = "ожидаем второго игрока (O)"
    elif game["status"] == "cancelled":
        status = "игра отменена"
    elif game["status"] == "done":
        w = winner(game["board"])
        status = "🤝 ничья!" if w == "draw" else f"🏆 победили {'❌' if w=='X' else '⭕'}!"
    else:
        status = f"ходит {'❌' if game['turn']=='X' else '⭕'}"
    return f"{title}\n\n{graphic}\n\n{status}"

def fresh_game(db, chat_id, x_id, private_ai):
    gid = secrets.token_hex(4)
    status = "playing" if private_ai else "waiting"
    o_id = -1 if private_ai else 0
    with db:
        db.execute("INSERT INTO games(id,chat_id,x_id,o_id,private_ai,status,created_at) VALUES(?,?,?,?,?,?,?)",
                   (gid,chat_id,x_id,o_id,int(private_ai),status,int(time.time())))
    return gid

def fetch_game(db, gid):
    row=db.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    return dict(row) if row else None

def edit_game(db, gid):
    g=fetch_game(db,gid)
    if not g or not g["message_id"]:
        return
    try:
        api("editMessageText", {"chat_id":g["chat_id"],"message_id":g["message_id"],
                                "text":display(g),"reply_markup":keyboard(g)})
    except Exception as exc:
        if "not modified" not in str(exc).lower():
            LOG.warning("Cannot edit game %s: %s",gid,exc)

def start(db, message):
    chat=message.get("chat", {})
    user=message.get("from", {})
    chat_id=chat.get("id")
    user_id=user.get("id")
    if not isinstance(chat_id,int) or not isinstance(user_id,int):
        return
    private_ai=chat.get("type")=="private"
    # An explicit solo mode is available in groups too.
    text=message.get("text","").strip()
    if text.lower().endswith(" solo"):
        private_ai=True
    gid=fresh_game(db,chat_id,user_id,private_ai)
    g=fetch_game(db,gid)
    try:
        result=api("sendMessage",{"chat_id":chat_id,"text":display(g),"reply_markup":keyboard(g),
                                  "reply_to_message_id":message.get("message_id")})
        msg_id=result.get("message_id",0)
        with db:
            db.execute("UPDATE games SET message_id=? WHERE id=?",(msg_id,gid))
    except Exception:
        # A bad reply_to_message_id should not prevent sending the game.
        try:
            result=api("sendMessage",{"chat_id":chat_id,"text":display(g),"reply_markup":keyboard(g)})
            with db:
                db.execute("UPDATE games SET message_id=? WHERE id=?",(result["message_id"],gid))
        except Exception:
            with db: db.execute("DELETE FROM games WHERE id=?", (gid,))
            raise

def minimax(board, ai_turn):
    w=winner(board)
    if w=="O": return 1
    if w=="X": return -1
    if w=="draw": return 0
    results=[]
    for pos,char in enumerate(board):
        if char!="-": continue
        next_board=board[:pos]+("O" if ai_turn else "X")+board[pos+1:]
        results.append(minimax(next_board,not ai_turn))
    return max(results) if ai_turn else min(results)

def choose_ai_move(board):
    moves=[]
    for pos,char in enumerate(board):
        if char!="-": continue
        trial=board[:pos]+"O"+board[pos+1:]
        moves.append((minimax(trial,False),pos))
    best=max(score for score,_ in moves)
    return random.choice([pos for score,pos in moves if score==best])

def callback(db, event):
    cb_id=event.get("id")
    user=event.get("from",{})
    user_id=user.get("id")
    msg=event.get("message") or {}
    chat_id=(msg.get("chat") or {}).get("id")
    message_id=msg.get("message_id")
    data=event.get("data","")
    parts=data.split(":")
    if len(parts)!=3 or parts[0]!="tt":
        return
    gid, action=parts[1:]
    notice="готово"
    changed=False
    try:
        # Serialized by this single polling process. One bot instance only.
        g=fetch_game(db,gid)
        if not g or g["chat_id"]!=chat_id or g["message_id"]!=message_id:
            notice="игра не найдена"
        elif action=="cancel":
            if user_id not in (g["x_id"],g["o_id"]):
                notice="только участник может завершить игру"
            elif g["status"] in ("done","cancelled"):
                notice="игра уже завершена"
            else:
                with db: db.execute("UPDATE games SET status='cancelled' WHERE id=?",(gid,))
                changed=True
                notice="игра завершена"
        elif action=="join":
            if g["status"]!="waiting":
                notice="игра уже началась"
            elif user_id==g["x_id"]:
                notice="дождись другого игрока"
            elif not isinstance(user_id,int) or user_id<=0:
                notice="неизвестный игрок"
            else:
                with db: db.execute("UPDATE games SET o_id=?, status='playing' WHERE id=?",(user_id,gid))
                changed=True
                notice="теперь ты играешь за O"
        elif action=="again":
            if user_id not in (g["x_id"],g["o_id"]):
                notice="новую игру может начать участник"
            else:
                # Avoid rewriting old game: start a fresh board.
                new_gid=fresh_game(db,g["chat_id"],user_id,bool(g["private_ai"]))
                new_g=fetch_game(db,new_gid)
                sent=api("sendMessage",{"chat_id":g["chat_id"],"text":display(new_g),
                                        "reply_markup":keyboard(new_g)})
                with db: db.execute("UPDATE games SET message_id=? WHERE id=?",(sent["message_id"],new_gid))
                notice="новая игра создана"
        elif action.startswith("m") and len(action)==2 and action[1].isdigit():
            idx=int(action[1])
            if g["status"]!="playing":
                notice="игра ещё не началась или уже завершена"
            elif g["board"][idx]!="-":
                notice="клетка занята"
            elif user_id!=(g["x_id"] if g["turn"]=="X" else g["o_id"]):
                notice="сейчас не твой ход"
            else:
                next_board=g["board"][:idx]+g["turn"]+g["board"][idx+1:]
                w=winner(next_board)
                next_turn="O" if g["turn"]=="X" else "X"
                status="done" if w else "playing"
                if g["private_ai"] and not w:
                    ai_idx=choose_ai_move(next_board)
                    next_board=next_board[:ai_idx]+"O"+next_board[ai_idx+1:]
                    status="done" if winner(next_board) else "playing"
                    next_turn="X"
                with db:
                    db.execute("UPDATE games SET board=?,turn=?,status=? WHERE id=?",
                               (next_board,next_turn,status,gid))
                changed=True
                notice="ход принят"
        else:
            notice="неизвестное действие"
    except Exception:
        LOG.exception("Callback failed")
        notice="ошибка обработки"
    finally:
        if cb_id:
            try: api("answerCallbackQuery",{"callback_query_id":cb_id,"text":notice})
            except Exception as exc: LOG.warning("callback answer failed: %s",exc)
    if changed:
        edit_game(db,gid)

def update(db,item):
    message=item.get("message") or item.get("edited_message")
    if message:
        txt=(message.get("text") or "").strip().lower()
        if txt in (".tt", ".tt solo", "/tt", "/tt solo") or txt.startswith("/tt@"):
            start(db,message)
    if "callback_query" in item:
        callback(db,item["callback_query"])

def configure_connection():
    """Ask for Bot API address and bot token in interactive mode.

    In noninteractive services use environment variables instead.
    """
    global BASE, TOKEN
    if sys.stdin.isatty():
        print("=== GoGram Tic-Tac-Toe (.tt) ===")
        entered_url = input(f"Bot API URL [{BASE}]: ").strip()
        if entered_url:
            BASE = entered_url.rstrip("/")
        if TOKEN:
            entered_token = getpass.getpass("Bot token [configured; Enter to keep]: ").strip()
            if entered_token:
                TOKEN = entered_token
        else:
            TOKEN = getpass.getpass("Bot token (hidden): ").strip()
    if not BASE.startswith(("http://", "https://")) or "/bot" in BASE:
        raise SystemExit("Bot API URL must be an origin like http://127.0.0.1:2500, without /botTOKEN")
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("Missing bot token. Set GOGRAM_BOT_TOKEN for systemd, or run in a terminal.")
    if BASE.startswith("http://") and not (
        BASE.startswith("http://127.0.0.1:") or BASE.startswith("http://localhost:")
    ):
        LOG.warning("Remote Bot API over HTTP exposes bot token; prefer a secure SSH tunnel or HTTPS")


def main():
    configure_connection()
    if not TOKEN or ":" not in TOKEN:
        raise SystemExit("Set GOGRAM_BOT_TOKEN from your OwpenGram bot creation")
    if not BASE.startswith("http://127.0.0.1:") and not BASE.startswith("http://localhost:"):
        LOG.warning("Bot API is not localhost; use a protected encrypted connection for remote bot tokens")
    db=db_conn()
    def stop(_sig,_frame):
        global RUN
        RUN=False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    LOG.info("Starting GoGram TT on %s",BASE)
    while RUN:
        try:
            row=db.execute("SELECT value FROM state WHERE key='offset'").fetchone()
            offset=int(row["value"]) if row else 0
            events=api("getUpdates",{"offset":offset,"timeout":25,"limit":50,
                                      "allowed_updates":["message","callback_query"]})
            for event in events:
                uid=event.get("update_id")
                if not isinstance(uid,int):
                    continue
                try: update(db,event)
                except Exception: LOG.exception("Failed update %s",uid)
                # Advance even on handler errors to avoid infinite processing loops.
                with db:
                    db.execute("INSERT INTO state(key,value) VALUES('offset',?) "
                               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(uid+1),))
        except (URLError,OSError,RuntimeError,ValueError) as exc:
            LOG.warning("Bot API unavailable: %s",exc)
            time.sleep(3)
    db.close()

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    main()
