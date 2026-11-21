# GORAM (GOR) — development currency for GoGram

This is **working server-side ledger code**, not a real blockchain, token, TON fork, or money. It is the first backend component for a possible GORAM currency.

- Unit: **GORAM**, ticker **GOR**.
- Precision: **1 GORAM = 1,000,000 microGORAM**.
- Persistent SQLite balances, atomic transfers, nonnegative balances and idempotent transaction request IDs.
- Internal-only HTTP service, bound to `127.0.0.1:2840`, protected by `GORAM_INTERNAL_TOKEN`.
- `GET /balance/<gogram_user_id>`, `POST /internal/transfer`, `POST /internal/mint`.
- The API has **no end-user authentication**; only the trusted GoGram backend may call it. **Do not expose port 2840 to the Internet or put the token into an iOS app.**
- A real deployment requires integration with GoGram's actual server-side identity and auth, transactions/history UI, rate limiting, security review, backups, and operational monitoring.
- The initial supply is 0. Minting here is for development/test balances only.

## Start on the GoGram server

```bash
cd /opt/owpengram-server
export GORAM_DB=/var/lib/goram/ledger.sqlite3
sudo mkdir -p /var/lib/goram
# Adjust ownership of /var/lib/goram for the service account before starting.
export GORAM_INTERNAL_TOKEN="$(openssl rand -hex 32)"
python3 path/to/goram.py
```

**Store the token securely** (e.g. a restricted environment file) and share it only with the trusted GoGram server backend. Restarting with a different token disconnects callers until they update theirs.

## Internal example calls

```bash
curl -H "Authorization: Bearer $GORAM_INTERNAL_TOKEN" http://127.0.0.1:2840/balance/123

curl -X POST http://127.0.0.1:2840/internal/mint \
  -H "Authorization: Bearer $GORAM_INTERNAL_TOKEN" -H 'Content-Type: application/json' \
  -d '{"to":"123","amount":10000000,"request_id":"test-credit-123-v1"}'

curl -X POST http://127.0.0.1:2840/internal/transfer \
  -H "Authorization: Bearer $GORAM_INTERNAL_TOKEN" -H 'Content-Type: application/json' \
  -d '{"from":"123","to":"456","amount":2500000,"request_id":"transfer-demo-v1"}'
```

This module does **not** modify GoGram gift Stars or Fragment and does **not** switch GRAM in a real blockchain. It is an explicitly labeled development ledger.
