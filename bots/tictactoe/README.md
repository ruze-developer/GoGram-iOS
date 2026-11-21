# GoGram tic-tac-toe bot — `.tt`

A working Python 3 bot built for the **OwpenGram Bot API** gateway listening on **127.0.0.1:2500** (this port belongs to the existing gateway; do not run the bot on it).

## Behaviour

- Send `.tt` in a group: a 3×3 board appears; the starter is ❌ and a second user taps **Join** to play ⭕.
- Send `.tt` in the bot's private chat: play against the computer.
- Send `.tt solo` in a group: play against the computer.
- Buttons update the same game message; turns and wins/ties are enforced.
- `/tt` is also supported.
- Games and `getUpdates` polling offset survive restart in local SQLite.
- This is a bot account: it will only see `.tt` in chats where it receives the user's messages.

## Start using the existing OwpenGram bot gateway

First, **create a bot account and obtain its token using your server's supported bot-management flow**. Do not put the token into a public GitHub repository, screenshot, or iOS client.

On the **same VPS** as OwpenGram:

```bash
cd /opt/owpengram-server
mkdir -p /opt/gogram-tictactoe
# copy bots/tictactoe/bot.py from this repository to /opt/gogram-tictactoe/bot.py
python3 --version
# Set the token in a root-protected environment file, not in the shell command history:
sudo install -m 600 /dev/null /etc/gogram-tictactoe.env
sudo nano /etc/gogram-tictactoe.env
```

Environment-file contents:

```ini
GOGRAM_BOT_TOKEN=BOT_TOKEN_FROM_YOUR_OWPENGRAM_SERVER
GOGRAM_BOT_API_URL=http://127.0.0.1:2500
GOGRAM_TT_DB=/opt/gogram-tictactoe/tt.sqlite3
```

Test directly with `set -a; source /etc/gogram-tictactoe.env; set +a; python3 /opt/gogram-tictactoe/bot.py` from an authorized root shell, or install the systemd unit below. Make sure the file is readable only by the service account.

## systemd

Install `gogram-tictactoe.service` into `/etc/systemd/system/` and then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gogram-tictactoe
sudo journalctl -u gogram-tictactoe -f
```

The supplied unit runs as an unprivileged account `gogram-bot`. Create that system user and chown `/opt/gogram-tictactoe` to it before starting.

## Chat automation / visibility

The exact `.tt` message is **not a Telegram bot command**. For the bot to receive arbitrary plain text in group chats, it must be added to those chats and granted message visibility / privacy mode turned off using the controls supported by the OwpenGram server. If chat automation is being used instead, configure it to forward or emit the **same .tt message to the bot's update stream**, with the real source chat/user context. The current OwpenGram business automation feature is not automatically wired to Bot API events.

**Do not expose** the local port 2500 or Bot API token publicly. The bot makes outbound calls to the localhost Bot API gateway.

## Status

The source is committed to GitHub, **not deployed or running on the VPS**. This connection lacks remote shell access and no bot token has been supplied. Your Bot API must also support getUpdates, sendMessage, editMessageText and answerCallbackQuery. No iOS rebuild is needed.
