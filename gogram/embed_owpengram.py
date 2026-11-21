#!/usr/bin/env python3
"""Fetch public OwpenGram server-info and embed into native PolySRV server list at build time.

Never copy a PRIVATE key into an app. Stop on bad/unreachable endpoint: no misleading IPA.
"""
import json
import os
import pathlib
import re
import sys
from urllib.request import Request, urlopen

ROOT = pathlib.Path(os.environ.get("SOURCE_DIR", "/Users/Shared/telegram-ios"))
APP_CONFIG = pathlib.Path(__file__).with_name("owpengram.json")
LIST = ROOT / "build-system/polysrv/servers.json"

def main():
    cfg = json.loads(APP_CONFIG.read_text())
    host = os.environ.get("GOGRAM_MTPROTO_HOST") or cfg["host"]
    port = int(os.environ.get("GOGRAM_MTPROTO_PORT") or cfg["port"])
    if not re.fullmatch(r"[a-zA-Z0-9.\-]+", host) or not 1 <= port <= 65535:
        raise ValueError("Invalid MTProto host or port")
    url = f"http://{host}:{port}/owpengram/server-info"
    print(f"Retrieving public OwpenGram config from {url}", flush=True)
    with urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "GoGram-iOS-CI"}), timeout=12) as res:
        if res.status != 200:
            raise ValueError(f"Server-info HTTP {res.status}")
        body = res.read(16000)
    info = json.loads(body)
    dc_id = info.get("dc_id")
    pub = info.get("rsa_public_key_pem")
    if type(dc_id) is not int or not 1 <= dc_id <= 5:
        raise ValueError("OwpenGram returned invalid dc_id (expected 1..5)")
    if not isinstance(pub, str) or not re.fullmatch(r"-----BEGIN RSA PUBLIC KEY-----\s+[A-Za-z0-9+/=\s]+-----END RSA PUBLIC KEY-----\s*", pub):
        raise ValueError("OwpenGram returned missing or invalid public RSA key")
    envelope = json.loads(LIST.read_text())
    server = {
        "id": cfg.get("server_id", "owpengram"),
        "name": info.get("name") or cfg.get("name", "OwpenGram"),
        "description": info.get("description") or cfg.get("description", "GoGram MTProto"),
        "host": host,
        "port": port,
        "rsaPublicKey": pub,
        "isTelegram": False,
        "isOfficial": False,
        "multiDc": False,
        "mainDcId": dc_id,
        "restrictToTcp": True,
        "dc": []
    }
    envelope["servers"] = [s for s in envelope["servers"] if s.get("id") != server["id"]]
    envelope["servers"].append(server)
    LIST.write_text(json.dumps(envelope, ensure_ascii=False, indent=2)+"\n")
    print(f"GoGram embedded {server['name']} at {host}:{port}, DC {dc_id}, public RSA key loaded.")
    print("Note: publishing source-to-server config is trusting this endpoint; verify server ownership and key out of band before distributing.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit("::error::Could not prepare OwpenGram configuration: "+str(exc)+". Verify the server is online, TELESRV_LISTEN, and GOGRAM_MTPROTO_PORT.")
