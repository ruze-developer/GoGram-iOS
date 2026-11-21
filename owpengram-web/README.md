# OwpenGram Web :80

Official frontend: https://github.com/owpengram/owpengram-web-client

The script builds upstream Telegram Web K based client *into the existing OwpenGram server source* and stages a named nginx reverse-proxy on port 80. It does not replace or restart the backend or nginx automatically.

On your VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/ruze-developer/GoGram-iOS/master/owpengram-web/install-owpengram-web.sh -o /root/install-owpengram-web.sh
less /root/install-owpengram-web.sh
sudo bash /root/install-owpengram-web.sh
```

Requirements: git, nginx, pnpm, Node >=22.18 or >=24.11, OwpenGram server source checkout (not just running binary). Set OWPENGRAM_SERVER_DIR if it is not in /root/owpengram-server, /opt/owpengram-server or /srv/owpengram-server.

After building, rebuild/restart the OwpenGram backend using your current launcher (not automatically done to avoid disruption). Set TELESRV_WEB_CLIENT_ENABLE=true and TELESRV_WEBSOCKET_ENABLE=true, and allow http://48.102.206.129 as a websocket origin if required. Then `sudo systemctl reload nginx`.

Open http://48.102.206.129/. For real users, use a domain with HTTPS/WSS and proper OTP delivery, not the development login code.

If nginx already has a vhost for this IP, the script refuses to overwrite it. Manually merge the proxy without destroying existing nginx routes.

**Not yet deployed to VPS**: Connected tools have no SSH or server shell execution. The script must be run on the VPS.