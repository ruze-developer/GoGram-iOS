# GoGram iOS

Native iOS messenger based on the open-source [Telegram iOS](https://github.com/TelegramMessenger/Telegram-iOS) code and the [PolySRV multiserver fork](https://github.com/roon9e/polysrv-ios).

**No WebView.** The PolySRV overlay adds a server picker and direct MTProto networking. The source is fetched by GitHub Actions and branded **GoGram** at build time.

## Build and download IPA

1. Open **Actions → Build GoGram iOS IPA**.
2. A push to `master` for this workflow or files under `gogram/` automatically starts the build. You can also use **Run workflow**.
3. When the build succeeds, open its run and download the **GoGram-iOS-IPA** artifact. Unzip the artifact to obtain `GoGram.ipa`.
4. The IPA is built with the upstream project's **fake code-signing profiles** and must be signed for your device using a trusted installation process. It is not App Store signed.

This is a large Bazel/Xcode build and success depends on the availability of a compatible GitHub macOS runner. A build run being triggered does **not** mean an IPA already exists.

## Connecting to your GoGram server

Use the **server picker** on the login screen and add the actual MTProto endpoint:

- Host: `48.102.206.129`
- Port: **the MTProto TCP port from `TELESRV_LISTEN`**, **not** port 80, 2600, 2800 or 8765.
- Main datacenter ID: use the value configured in your server.
- RSA public key: use your GoGram server's MTProto public key (do not send private keys).

The default list still contains official Telegram. This client will not connect to your GoGram backend until the correct endpoint and public key are entered.

## Optional API credentials

Set repository **Actions secrets** `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` to your own development credentials. These are injected only into the temporary build tree. If absent, the project retains the public upstream build configuration; for distribution, replace it with your own credentials.

## Safety

There is an unresolved security problem in the user's GoGram server: one user's login code was reportedly visible to other accounts. **Fix that before using or sharing the client for real logins.** A client app cannot fix server-side OTP broadcast leaks.

Do not enter verification codes on sites offering unowned virtual phone numbers. This project is a native-client build workflow, not a phone/SMS service.

## Credits and license

Based on Telegram iOS and PolySRV. Retain upstream license and attribution. Do not use Telegram branding or logos in redistributed builds.
