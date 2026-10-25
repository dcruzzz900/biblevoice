# BibleVoice
Voice-driven Bible app for churches. Python (FastAPI + faster-whisper + SQLite FTS5), mobile-first UI.

## Setup
    pip install -r requirements.txt
    python import_bible.py KJV "King James Version" kjv.csv --default
    python import_bible.py WEB "World English Bible" web.csv
    uvicorn main:app --host 0.0.0.0 --port 8000
Open http://<computer-ip>:8000 on any phone/laptop on the church Wi-Fi.
First run downloads the Whisper model once; after that everything works with no internet.
(Browsers only allow the microphone on localhost or HTTPS: on a LAN use HTTPS, e.g. `caddy reverse-proxy --from :8443 --to :8000`.)

## Accuracy tips
- WHISPER_MODEL=medium (default small) for stronger Nigerian-accent accuracy.
- Use a lapel/pulpit mic. Live mode checks every 7 seconds and opens verses automatically.
- Whisper is primed with Bible book names, so "Genesys" / "Ephesians" style mishearings still resolve.

## Bible versions
Public-domain (KJV, WEB, ASV, YLT) can be imported freely. NIV, ESV, NASB, NKJV, AMP, MSG, NLT, CSB are
copyrighted: import only text you are licensed to use (e.g. via the publishers' or API.Bible licences).

## Accounts and live following
- First account created = **admin** (make this the pastor/media head). Everyone else signs up as a **member**.
- Admin and media team open **Admin** on the home screen (or `/admin`): connected devices, the media team, password resets and the service log. (The old OPERATOR_PIN is gone.)
- Hosts tap **Operator** (live mode) so the mic listens to the pastor. Each verse reaches every member's phone, shown in the member's own Bible version.
- Favorites, notes and recent searches are saved to the member's account, so they follow them to a new phone.
- Passwords are stored hashed (scrypt). Use HTTPS if the server is reachable from the internet.

## Phones for members
- Quick: open the church URL in Chrome/Safari, then "Add to Home Screen" (installable PWA).
- Native Android/iOS: install Node, then
      npm init -y && npm i @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
      (set your server address in capacitor.config.json, then:) npx cap add android && npx cap add ios && npx cap sync
      npx cap open android   # build APK/AAB in Android Studio;  npx cap open ios   # needs a Mac + Xcode
  Add microphone permission text in the iOS Info.plist (NSMicrophoneUsageDescription).
- Members away from church Wi-Fi need the server reachable over HTTPS (e.g. a Cloudflare Tunnel to the church computer).

## Yoruba / Hausa / Igbo
Import with `--lang=yo|ha|ig` (CSV with book numbers 1-66), or find them via `python api_bible.py list yor|hau|ibo`.
The pastor is recognised in English (WHISPER_LANG=en; Whisper supports Yoruba and Hausa but not Igbo), members read in their own language.

## Auto-detect (every member's phone)
Tap **Auto-detect** on the home screen. The phone listens to the room: the pastor's voice, the church speakers, or ordinary talk.
- Chrome/Android uses on-phone speech recognition tuned to Nigerian English (`en-NG`); it needs internet. With no internet it switches to the church server's Whisper (max 2 jobs at once; silent audio is never sent).
- Only confident references open by themselves ("John 3:16", "turn to Romans chapter 8"). Everyday words that are also book names (Mark, Job, John, Acts...) need a verse number or a cue like "turn to".
- Topics ("tithes", "Goliath", "Melchizedek") appear as tap-to-open suggestion buttons, never as a screen takeover. Edit the `TOPICS` list in `main.py` to add your own.
- Host broadcast is still the most reliable way to reach everyone in a large congregation; Auto-detect is each member's own backup.

## Quick start (church computer)
1. Install Python 3.10+. Connect to the internet once (downloads the speech model the first time).
2. Import a Bible: `python import_bible.py KJV "King James Version" kjv.csv --default` (CSV, JSON or plain-text lines; it reports how many of the 66 books it found).
3. Double-click `start.bat` (Windows) or run `./start.sh`. It sets everything up, makes an HTTPS certificate and prints the address for members.
   If the computer's IP address changes, just start it again; it makes a new certificate.
4. Members open the address, accept the one-time certificate warning, create an account, then "Add to Home Screen".

## Projector / big screen
On the screen's computer open `https://<address>:8443/screen`, sign in with a member account made just for the screen, and double-click for full screen.
It shows whatever the pastor's broadcast opens, in large text that shrinks to fit long passages. Choose the version with `/screen?v=NIV`.

## Admin page (`/admin`)
- **Admin only:** make a member a broadcaster (host) or back to member, reset a forgotten password, remove a member.
- **Pastor / media team:** see how many devices are connected and what is on screen now, and read the **service log**: every verse broadcast, with time and who sent it.
  **Copy notes** or **Download .txt** gives a ready sermon-notes list for the day.
- Five wrong passwords for a name locks that name out for 5 minutes.

## Before Sunday: health check
`python selfcheck.py --download` once while online (fetches the speech model), then `python selfcheck.py --whisper` with the internet OFF to prove it works offline.
`python selfcheck.py` alone checks Bibles, the reference parser, search, admin account and HTTPS certificate, and tells you how to fix anything red.

### Dry-run checklist (do this mid-week, not on Sunday)
1. Run `selfcheck.py`; fix every ✗.  2. Start the app; create the pastor's account (first = admin) and one account for the projector.
3. Two phones join with their own accounts; one picks a different Bible version.  4. Projector opens `/screen`.
5. Pastor's phone: Operator mode; say "turn to John chapter 3 verse 16". All phones and the projector should show it, each in its own version.
6. Say ordinary sentences ("I met Mark yesterday"): nothing should open.  7. Turn on Auto-detect on a member phone and play the pastor's voice through the speakers.
8. Switch the church router's internet off and repeat step 5.  9. Check `/admin` shows the log.  10. Note which steps failed and tell me.

## Hosting online (Docker)
1. Server with Docker, a domain pointing to it, ports 80 and 443 open. Copy `.env.example` to `.env` and set `DOMAIN`.
2. `docker compose up -d --build`
3. Import a Bible: `docker compose run --rm -v "$PWD":/in app python import_bible.py KJV "King James Version" /in/kjv.csv --default`
4. Speech recognition runs on that server's CPU, so pick enough power (4+ cores) or set `WHISPER_MODEL=base` (faster, less accurate).
Sign-ins last 60 days (`SESSION_DAYS`). **Sign out** on a phone can also sign out all of that member's devices.

## Measure accuracy with your own voices
`python tests/test_parser.py` checks 34 ways of saying references (and ordinary talk that must be ignored). Add lines for anything you find missed.
`python eval_audio.py recordings/` runs the real speech engine on clips you record (see the top of that file) and reports what it heard and whether the right verse opened.
Compare `--model=small` vs `--model=medium`, and `--no-prompt`, to choose settings for your church. Do this with the pastor's actual voice and your sound system.

## Native app speech (Android / iOS)
In the Capacitor app, Auto-detect uses the phone's own speech recognizer. After the steps above also run `npm i @capacitor-community/speech-recognition && npx cap sync`.
iOS: add `NSSpeechRecognitionUsageDescription` and `NSMicrophoneUsageDescription` to Info.plist. Android: allow the microphone.
Whether it works without internet depends on the phone: Android needs its offline English speech pack (Settings > Google > Offline speech recognition). Test in airplane mode.
Known limit: some Android phones make a small sound each time recognition restarts. If that bothers people, use the server speech (a phone without this plugin does so automatically).
This native code is written but has not been run on a phone.

## Getting Bible text legally
**Hausa, Yoruba, Igbo** (eBible.org, free under Creative Commons CC BY-SA 4.0, by Biblica):
download the **USFM zip** from the translation's page (ids `hausa`, `yor`, `ibo`; Hausa New Testament only: `hauulb`). The Hausa and Igbo pages list USFM zips; on the Yoruba page look under "Show formats for developers". Then:

    python import_bible.py HAU "Hausa Contemporary Bible" hausa_usfm.zip --lang=ha --credit="Biblica Open Hausa Contemporary Bible, CC BY-SA 4.0"
    python import_bible.py YOR "Yoruba Contemporary Bible" yor_usfm.zip   --lang=yo --credit="Biblica Open Yoruba Contemporary Bible, CC BY-SA 4.0"
    python import_bible.py IBO "Igbo Contemporary Bible"   ibo_usfm.zip   --lang=ig --credit="Biblica Open Igbo Contemporary Bible, CC BY-SA 4.0"

The credit line shows under each version on the Versions screen. Read the licence on the eBible page: it asks for attribution and has rules about the Biblica trademark.
The importer removes footnotes and headings, which may count as altering the text. If in doubt, ask Biblica (open.bible/contact-us).

**English public-domain** (KJV, ASV, YLT, BBE...): the `scrollmapper/bible_databases` project on GitHub lists 140 translations (its code is MIT-licensed; each translation's own licence is in its `translations` table).
Download the CSV or JSON file for a translation and import it. Its file layout changed in 2025, and I could not open its folders to confirm the exact format: if an import says "No verses found", send me the first lines of the file.
Beware repositories that bundle ESV, NASB, AMP or NIV text without a licence. Do not use those.

## Light server mode (cheap or free hosting)
The server does no speech recognition at all. The **pastor's phone** recognises speech and sends only text; the server finds the verse and broadcasts it to members.
- Start: `start-light.bat` / `./start-light.sh` (plain HTTP on port 8000; put a tunnel or host in front for HTTPS). Docker: set `LIGHT=1` in `.env`. It uses `requirements-light.txt` (no Whisper), so a few hundred MB of RAM is plenty.
- The pastor signs in on their phone and taps **Operator**. It listens and broadcasts each verse it hears (same safeguards as before: ordinary talk is ignored).
- Needs **Chrome on Android with internet** (Chrome sends the audio to Google's speech service), or the native BibleVoice app. iPhone Safari speech is unreliable, so use an Android phone for the pastor.
- Trade-off: no offline speech on the server and no Whisper accuracy tuning. For a church with unreliable internet, the full mode on the church computer is still better.
- Free hosts usually wipe the disk on restart, which would delete accounts and the Bible. Pick one with a persistent disk, or re-import the Bible and recreate accounts after each restart.
- Check anytime: `GET /api/config` says `"speech": "phone"` (light) or `"server"` (full).

## Deploy on Render
Render runs the **light server** (phones do the speech recognition, see above), so no Whisper is needed.
1. **Put the project on GitHub** (a private repo is fine). Add your Bible file(s) to `bibles/` and list them in `bibles/manifest.json` (public-domain or licensed text only).
2. **Create the service:** in Render choose New, then Blueprint, connect the repo. Render reads `render.yaml` from the repo root and asks you for two secrets:
   `ADMIN_SETUP_CODE` (needed to create the very first, admin account) and `JOIN_CODE` (members must enter it to register). Pick codes only your church knows.
3. **Wait for the deploy**, then open `https://<your-service>.onrender.com`. Create the first account with the admin setup code: that is the admin.
4. Give members the web address and the join code. The pastor signs in on an **Android phone in Chrome** and taps **Operator**.
5. Members can "Add to Home Screen". The projector opens `/screen` with its own member account.

**Free vs paid.** `render.yaml` is the free plan: fine for a rehearsal, **not for real services**. Free instances sleep after 15 minutes without traffic and lose every change on their filesystem when they sleep or restart. Accounts, favorites, notes and the service log would vanish, and the Bible is re-imported on each start. Waking up also takes up to a minute, so open the site 10 minutes before a service.
For real use, rename `render-paid.yaml` to `render.yaml` before creating the Blueprint. It uses a paid instance with a 1 GB persistent disk mounted at `/data` (`DATA_DIR`), so data survives. Check Render's pricing page for the current cost.
