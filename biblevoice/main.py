"""BibleVoice backend: FastAPI + SQLite (FTS5) + faster-whisper. Runs fully offline once models/Bibles are installed."""
import os, re, sqlite3, tempfile, difflib, asyncio, json, secrets, time, hashlib, importlib.util
import api_bible
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

ROOT = Path(__file__).parent
DB = Path(os.getenv("DATA_DIR", ROOT)) / "bible.db"  # DATA_DIR lets Docker keep the database on a volume
# LIGHT=1 (or no faster-whisper installed) = "light server": phones do the speech recognition and send only text. Needs very little RAM/CPU.
HAVE_WHISPER = os.getenv("LIGHT") != "1" and importlib.util.find_spec("faster_whisper") is not None
MODEL_NAME = os.getenv("WHISPER_MODEL", "small")  # "medium" is more accurate on Nigerian accents, if your PC can handle it

BOOKS = ("Genesis,Exodus,Leviticus,Numbers,Deuteronomy,Joshua,Judges,Ruth,1 Samuel,2 Samuel,1 Kings,2 Kings,1 Chronicles,2 Chronicles,"
 "Ezra,Nehemiah,Esther,Job,Psalms,Proverbs,Ecclesiastes,Song of Solomon,Isaiah,Jeremiah,Lamentations,Ezekiel,Daniel,Hosea,Joel,Amos,"
 "Obadiah,Jonah,Micah,Nahum,Habakkuk,Zephaniah,Haggai,Zechariah,Malachi,Matthew,Mark,Luke,John,Acts,Romans,1 Corinthians,2 Corinthians,"
 "Galatians,Ephesians,Philippians,Colossians,1 Thessalonians,2 Thessalonians,1 Timothy,2 Timothy,Titus,Philemon,Hebrews,James,1 Peter,"
 "2 Peter,1 John,2 John,3 John,Jude,Revelation").split(",")
ALIAS = {"psalm": "Psalms", "songs of solomon": "Song of Solomon", "song of songs": "Song of Solomon",
         "revelations": "Revelation", "apocalypse": "Revelation", "gen": "Genesis", "matt": "Matthew"}
NAMES = {b.lower(): i + 1 for i, b in enumerate(BOOKS)}
NAMES.update({k: BOOKS.index(v) + 1 for k, v in ALIAS.items()})

U = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
T = {w: i * 10 for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
ORD = {"first": "1", "1st": "1", "second": "2", "2nd": "2", "third": "3", "3rd": "3"}
STOP = set("the a an of and to in is was for that this he she it they we you i said say book verse verses chapter chapters read turn open please let us bible about your my our says pastor brother sister amen".split())


def nums(text):
    """'psalm twenty three' -> 'psalm 23', 'john three sixteen' -> 'john 3 16'"""
    out, acc, h = [], None, False
    for w in text.split() + ["#"]:
        v = U.get(w, T.get(w))
        if w == "hundred" and acc is not None: acc *= 100; h = True; continue
        if w == "and" and h: continue
        if v is not None:
            if acc is not None and ((h and v < 100 and acc % 100 == 0) or (20 <= acc < 100 and acc % 10 == 0 and 0 < v < 10) or (acc > 100 and acc % 100 and acc % 10 == 0 and 0 < v < 10)):
                acc += v; h = False; continue
            if acc is not None: out.append(str(acc))
            acc, h = v, False; continue
        if acc is not None: out.append(str(acc)); acc, h = None, False
        if w != "#": out.append(ORD.get(w, w))
    return " ".join(out)


def find_book(words):
    for i in range(len(words)):
        for n in (3, 2, 1):
            if any(w.isdigit() for w in words[i + 1:i + n]): continue  # numbers after the name belong to the reference
            cand = " ".join(words[i:i + n])
            hit = NAMES.get(cand)
            if not hit and len(cand) >= 5:
                m = difflib.get_close_matches(cand, NAMES, 1, 0.82)  # tolerates accent/mishearing: "genesys", "ephesians"
                hit = NAMES[m[0]] if m else None
            if hit: return hit, min(i + n, len(words))
    return None, 0


AMBIG = {"job", "mark", "luke", "john", "james", "acts", "ruth", "amos", "jude"}  # also everyday names/words: need stronger evidence
CUES = {"turn", "open", "read", "chapter", "verse", "verses", "book", "bible", "scripture", "reading", "gospel", "according"}
TOPICS = [(r"tithes?|tithing", "Tithes", "Malachi 3:10"), (r"offerings?", "Giving", "2 Corinthians 9:7"), (r"melchizedek", "Melchizedek", "Genesis 14:18-20"),
 (r"goliath", "David and Goliath", "1 Samuel 17:45"), (r"lord.?s prayer", "The Lord's Prayer", "Matthew 6:9-13"), (r"ten commandments", "Ten Commandments", "Exodus 20:1-17"),
 (r"beatitudes", "Beatitudes", "Matthew 5:3-12"), (r"great commission", "Great Commission", "Matthew 28:19-20"), (r"good samaritan", "Good Samaritan", "Luke 10:25-37"),
 (r"prodigal", "Prodigal Son", "Luke 15:11-32"), (r"noah|the ark", "Noah", "Genesis 6:9-22"), (r"red sea", "Red Sea", "Exodus 14:21-22"), (r"lazarus", "Lazarus", "John 11:43-44"),
 (r"born again", "Born again", "John 3:3"), (r"holy spirit", "Holy Spirit", "Acts 2:1-4"), (r"faith comes", "Faith", "Romans 10:17"), (r"fruit of the spirit", "Fruit of the Spirit", "Galatians 5:22-23"),
 (r"armou?r of god", "Armor of God", "Ephesians 6:10-18"), (r"love is patient|love chapter", "Love", "1 Corinthians 13:4-7"), (r"shepherd", "The Lord is my shepherd", "Psalms 23"),
 (r"mustard seed", "Mustard seed", "Matthew 17:20"), (r"samson", "Samson", "Judges 16:28-30"), (r"lions.? den", "Daniel and the lions", "Daniel 6:16-23")]  # extend freely


def parse(text, strict=False):
    # "16-17" is a range, but "twenty-two" is just a number; "and/from verse 5" is filler
    t = re.sub(r"\b(?:and|from|at|starting)\s+(?=(?:verses?|vs)\b)", "", nums(re.sub(r"[^a-z0-9: ]", " ", re.sub(r"(\d)\s*[-–—]\s*(\d)", r"\1 to \2", text.lower())).replace(":", " ")))
    words = t.split()
    book, end = find_book(words)
    if not book: return None
    rest = " ".join(words[end:])
    m = re.match(r"(?:chapter\s+)?(\d+)(?:\s+(?:verses?|vs|v)\s+|\s+)?(\d+)?(?:\s+(?:to|through|till|-)\s+(\d+))?", rest)
    if strict:  # ambient listening: ordinary talk must not open verses ("I met Mark", "good job 5 people")
        cue, amb = any(w in CUES for w in words), words[end - 1] in AMBIG and not (end > 1 and words[end - 2].isdigit())
        if not m and (amb or not cue): return None
        if m and amb and not (m.group(2) or cue): return None
    ch, v1, v2 = (int(x) if x else None for x in m.groups()) if m else (1, None, None)
    return book, ch, v1, v2


def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c


def db_init():
    c = db()
    c.executescript("""CREATE TABLE IF NOT EXISTS versions(code TEXT PRIMARY KEY,name TEXT,is_default INT DEFAULT 0);
    CREATE TABLE IF NOT EXISTS verses(id INTEGER PRIMARY KEY,version TEXT,book INT,chapter INT,verse INT,text TEXT);
    CREATE INDEX IF NOT EXISTS ix ON verses(version,book,chapter,verse);
    CREATE VIRTUAL TABLE IF NOT EXISTS vfts USING fts5(text,content='verses',content_rowid='id');
    CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,ref TEXT,version TEXT,at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS favorites(ref TEXT,version TEXT,PRIMARY KEY(ref,version));
    CREATE TABLE IF NOT EXISTS notes(ref TEXT PRIMARY KEY,note TEXT);""")
    try: c.execute("ALTER TABLE versions ADD COLUMN api_id TEXT")
    except sqlite3.OperationalError: pass
    c.commit(); c.close()


db_init()
_c = db()
_c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT UNIQUE COLLATE NOCASE,pw TEXT,salt TEXT,role TEXT DEFAULT 'member');
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,uid INT);
CREATE TABLE IF NOT EXISTS user_data(uid INTEGER PRIMARY KEY,data TEXT);
CREATE TABLE IF NOT EXISTS service_log(id INTEGER PRIMARY KEY,at INT,ref TEXT,by TEXT);""")
try: _c.execute("ALTER TABLE versions ADD COLUMN lang TEXT DEFAULT 'en'")  # en / yo / ha / ig
except sqlite3.OperationalError: pass
try: _c.execute("ALTER TABLE versions ADD COLUMN credit TEXT DEFAULT ''")  # attribution line (CC BY-SA etc.)
except sqlite3.OperationalError: pass
try: _c.execute("ALTER TABLE sessions ADD COLUMN created INT")
except sqlite3.OperationalError: pass
_c.commit(); _c.close()
app = FastAPI(title="BibleVoice")
_model = None


def whisper():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_NAME, compute_type="int8")  # CPU-friendly; cached locally after first download
    return _model


PROMPT = ("Nigerian pastor preaching in English. Scripture references: " + ", ".join(BOOKS) +
          ". Moses, Abraham, Melchizedek, Jerusalem, Bethlehem, tithes and offerings, Malachi 3:10, John 3:16, Psalm 23.")


def fetch(version, book, ch, v1=None, v2=None):
    q, a = "SELECT verse,text FROM verses WHERE version=? AND book=? AND chapter=?", [version, book, ch]
    if v1: q += " AND verse BETWEEN ? AND ?"; a += [v1, v2 or v1]
    return [dict(r) for r in db().execute(q + " ORDER BY verse", a)]


def get_passage(version, book, ch, v1=None, v2=None):
    vs = fetch(version, book, ch, v1, v2)
    if not vs and api_bible.KEY:  # not stored locally: fetch online once, then it works offline
        c = db(); r = c.execute("SELECT api_id FROM versions WHERE code=?", (version,)).fetchone()
        if r and r["api_id"]:
            try: api_bible.cache_chapter(c, version, r["api_id"], book, ch); vs = fetch(version, book, ch, v1, v2)
            except Exception: pass
    return vs


def build(version, book, ch, v1=None, v2=None):
    vs = get_passage(version, book, ch, v1, v2)
    if not vs: return None
    ref = f"{BOOKS[book-1]} {ch}" + (f":{v1}" + (f"-{v2}" if v2 else "") if v1 else "")
    return {"type": "passage", "ref": ref, "version": version, "verses": vs, "b": book, "c": ch, "v1": v1, "v2": v2}


def resolve(text, version):
    p = parse(text)
    if p:
        res = build(version, *p)
        if res: return res
    terms = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]
    if not terms: return {"type": "none"}
    fq = " OR ".join(f'"{w}"*' for w in terms[:6])  # people, places, tithes, topics: full-text search
    rows = db().execute("SELECT v.book,v.chapter,v.verse,v.text FROM vfts JOIN verses v ON v.id=vfts.rowid "
                        "WHERE vfts MATCH ? AND v.version=? ORDER BY rank LIMIT 20", (fq, version)).fetchall()
    return {"type": "search", "query": text, "version": version,
            "results": [{"ref": f"{BOOKS[r['book']-1]} {r['chapter']}:{r['verse']}", "text": r["text"]} for r in rows]}


def detect(text, version):
    """Ambient mode: open only confident references; surface topics (tithes, Goliath...) as tap-to-open suggestions; ignore the rest."""
    p = parse(text, strict=True)
    if p:
        r = build(version, *p)
        if r: return {**r, "action": "open"}
    low, items = text.lower(), []
    for pat, label, ref in TOPICS:
        if re.search(rf"\b(?:{pat})\b", low) and build(version, *parse(ref)): items.append({"label": label, "ref": ref})
    return {"type": "suggest", "action": "suggest", "items": items[:3]} if items else {"type": "none", "action": "ignore"}


@app.post("/api/detect")  # members' phones send recognised TEXT here (tiny, so hundreds of phones are fine)
def detect_ep(text: str = Form(...), version: str = Form("KJV"), token: str = Form(...), broadcast: str = Form("0")):
    u = who(token); res = detect(text[:500], version)
    if broadcast == "1" and u["role"] in ("admin", "host") and res.get("action") == "open": broadcast_verse(res, u["name"])  # pastor's phone, light mode
    return res


@app.get("/api/config")
def config(): return {"speech": "server" if HAVE_WHISPER else "phone"}  # who does the speech recognition


@app.get("/api/versions")
def versions(): return [dict(r) for r in db().execute("SELECT code,name,is_default,lang,credit FROM versions ORDER BY is_default DESC,code")]


@app.get("/api/lookup")
def lookup(q: str, version: str = "KJV"): return resolve(q, version)


subs = set()
FAILS = {}
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "60"))  # phones stay signed in this long
SEM = asyncio.Semaphore(2)  # at most 2 Whisper jobs at once
svc = {"live": False, "current": None, "last": ("", 0.0)}


def state(): return {"t": "state", "live": svc["live"], "current": svc["current"]}


def publish(ev):
    for q in list(subs): q.put_nowait(ev)


def broadcast_verse(res, by=""):
    if res.get("type") != "passage": return
    now = time.time()
    if svc["last"][0] == res["ref"] and now - svc["last"][1] < 25: return  # live mode can hear the same verse twice
    svc["last"], svc["live"] = (res["ref"], now), True
    svc["current"] = {k: res[k] for k in ("ref", "b", "c", "v1", "v2")}
    c = db(); c.execute("INSERT INTO service_log(at,ref,by) VALUES(?,?,?)", (int(now), res["ref"], by)); c.commit()  # the Sunday log
    publish({"t": "verse", "live": True, **svc["current"]})


def hash_pw(pw, salt): return hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()


def who(token):
    r = db().execute("SELECT u.id,u.name,u.role FROM sessions s JOIN users u ON u.id=s.uid WHERE s.token=? AND (s.created IS NULL OR s.created>?)",
                       (token or "", time.time() - SESSION_DAYS * 86400)).fetchone()
    if not r: raise HTTPException(401, "Please sign in")
    return dict(r)


def host(token):
    u = who(token)
    if u["role"] not in ("admin", "host"): raise HTTPException(403, "Pastor / media team only")
    return u


def session(c, uid):
    t, now = secrets.token_urlsafe(32), int(time.time())
    c.execute("DELETE FROM sessions WHERE created<?", (now - SESSION_DAYS * 86400,))  # tidy expired sign-ins
    c.execute("INSERT INTO sessions(token,uid,created) VALUES(?,?,?)", (t, uid, now)); c.commit(); return t


@app.post("/api/register")
def register(name: str = Form(...), password: str = Form(...), code: str = Form("")):
    name, c = name.strip(), db()
    if len(name) < 2 or len(password) < 6: raise HTTPException(400, "Name 2+ characters, password 6+ characters")
    if c.execute("SELECT 1 FROM users WHERE name=?", (name,)).fetchone(): raise HTTPException(409, "That name is taken")
    salt = secrets.token_hex(16); first = not c.execute("SELECT 1 FROM users").fetchone()
    need = os.getenv("ADMIN_SETUP_CODE") if first else os.getenv("JOIN_CODE")  # public URL: stop strangers claiming admin or joining
    if need and not secrets.compare_digest(code.strip().encode(), need.strip().encode()):
        raise HTTPException(403, "Enter the admin setup code" if first else "Enter your church’s join code (ask your pastor)")
    role = "admin" if first else "member"  # first account = admin
    uid = c.execute("INSERT INTO users(name,pw,salt,role) VALUES(?,?,?,?)", (name, hash_pw(password, salt), salt, role)).lastrowid
    return {"token": session(c, uid), "role": role, "name": name}


@app.post("/api/login")
def login(name: str = Form(...), password: str = Form(...)):
    c, k, now = db(), name.strip().lower(), time.time(); n, t = FAILS.get(k, (0, 0))
    if n >= 5 and now - t < 300: raise HTTPException(429, "Too many wrong attempts. Wait 5 minutes.")
    r = c.execute("SELECT * FROM users WHERE name=?", (name.strip(),)).fetchone()
    if not r or not secrets.compare_digest(hash_pw(password, r["salt"]), r["pw"]):
        FAILS[k] = (n + 1 if now - t < 300 else 1, now); raise HTTPException(401, "Wrong name or password")
    FAILS.pop(k, None)
    return {"token": session(c, r["id"]), "role": r["role"], "name": r["name"]}


def admin(token):
    u = who(token)
    if u["role"] != "admin": raise HTTPException(403, "Admin only")
    return u


@app.get("/api/admin/stats")
def stats(token: str):
    u = host(token); d = {"role": u["role"], "online": len(subs), "live": svc["live"], "current": (svc["current"] or {}).get("ref")}
    if u["role"] == "admin": d["users"] = [dict(r) for r in db().execute("SELECT name,role FROM users ORDER BY role,name")]
    return d


@app.post("/api/admin/reset")  # forgotten password
def reset(token: str = Form(...), name: str = Form(...), password: str = Form(...)):
    admin(token)
    if len(password) < 6: raise HTTPException(400, "Password needs 6+ characters")
    c = db(); r = c.execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()
    if not r: raise HTTPException(404, "No such member")
    salt = secrets.token_hex(16); c.execute("UPDATE users SET pw=?,salt=? WHERE id=?", (hash_pw(password, salt), salt, r["id"]))
    c.execute("DELETE FROM sessions WHERE uid=?", (r["id"],)); c.commit(); return {"ok": 1}


@app.post("/api/admin/delete")
def delete_user(token: str = Form(...), name: str = Form(...)):
    admin(token); c = db(); r = c.execute("SELECT id FROM users WHERE name=? AND role!='admin'", (name,)).fetchone()
    if not r: raise HTTPException(404, "No such member (admins can't be removed)")
    for q in ("DELETE FROM sessions WHERE uid=?", "DELETE FROM user_data WHERE uid=?", "DELETE FROM users WHERE id=?"): c.execute(q, (r["id"],))
    c.commit(); return {"ok": 1}


@app.get("/api/log")
def service_log(token: str, limit: int = 500):
    host(token); return [dict(r) for r in db().execute("SELECT at,ref,by FROM service_log ORDER BY id DESC LIMIT ?", (min(limit, 2000),))]


@app.post("/api/logout")
def logout(token: str = Form(...), everywhere: str = Form("0")):
    u = who(token); c = db()
    if everywhere == "1": c.execute("DELETE FROM sessions WHERE uid=?", (u["id"],))  # lost phone: sign out all devices
    else: c.execute("DELETE FROM sessions WHERE token=?", (token,))
    c.commit(); return {"ok": 1}


@app.get("/api/me")
def me(token: str): u = who(token); return {"name": u["name"], "role": u["role"]}


@app.post("/api/role")
def role(token: str = Form(...), name: str = Form(...), role: str = Form("host")):
    if who(token)["role"] != "admin" or role not in ("host", "member"): raise HTTPException(403, "Admin only")
    c = db(); n = c.execute("UPDATE users SET role=? WHERE name=? AND role!='admin'", (role, name.strip())).rowcount; c.commit()
    if not n: raise HTTPException(404, "No member with that name")
    return {"ok": 1}


@app.get("/api/sync")  # favorites, notes and recent follow the member to any phone they sign in on
def sync_get(token: str):
    r = db().execute("SELECT data FROM user_data WHERE uid=?", (who(token)["id"],)).fetchone(); return json.loads(r["data"]) if r else {}


@app.post("/api/sync")
def sync_set(token: str = Form(...), data: str = Form(...)):
    json.loads(data); c = db(); c.execute("INSERT OR REPLACE INTO user_data VALUES(?,?)", (who(token)["id"], data[:300000])); c.commit(); return {"ok": 1}


@app.post("/api/push")
async def push(token: str = Form(...), q: str = Form(...), version: str = Form("KJV")):
    u = host(token)
    res = resolve(q, version); broadcast_verse(res, u["name"]); return res  # (was calling a renamed function)


@app.post("/api/service/end")
async def end(token: str = Form(...)):
    host(token)
    svc.update(live=False, current=None, last=("", 0.0)); publish({"t": "end"}); return {"ok": 1}


@app.get("/api/passage")
def passage(b: int, c: int, version: str = "KJV", v1: int = None, v2: int = None):
    for code in [version] + [v["code"] for v in versions()]:  # member's version first, else any installed version that has it
        r = build(code, b, c, v1, v2)
        if r: return r
    return {"type": "none"}


@app.get("/api/stream")
async def stream(token: str):
    who(token); q = asyncio.Queue(); subs.add(q)

    async def gen():
        try:
            yield f"data: {json.dumps(state())}\n\n"
            while True:
                try: yield f"data: {json.dumps(await asyncio.wait_for(q.get(), 20))}\n\n"
                except asyncio.TimeoutError: yield ": ping\n\n"
        finally: subs.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/voice")
async def voice(audio: UploadFile = File(...), version: str = Form("KJV"), token: str = Form(""), broadcast: str = Form("0"), ambient: str = Form("0")):
    u, data = who(token), await audio.read()  # sign-in required: transcription is the expensive part
    if not HAVE_WHISPER: raise HTTPException(503, "Light mode: speech recognition runs on phones")

    def run():
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f: f.write(data); path = f.name
        try:
            segs, _ = whisper().transcribe(path, language=os.getenv("WHISPER_LANG", "en"), initial_prompt=PROMPT, vad_filter=True, beam_size=5)
            return " ".join(s.text for s in segs).strip()
        finally: os.unlink(path)
    if ambient == "1" and SEM.locked(): return {"type": "none", "action": "ignore", "busy": True}  # protect the server: phones skip a beat, never queue up
    async with SEM: text = await asyncio.to_thread(run)  # keep the server responsive for members while transcribing
    strict = ambient == "1" or broadcast == "1"  # never broadcast a guess from ordinary talk to the whole church
    res = (detect(text, version) if strict else resolve(text, version)) if text else {"type": "none"}
    if broadcast == "1" and u["role"] in ("admin", "host") and res.get("action") == "open": broadcast_verse(res, u["name"])  # only live mode by a host reaches members
    return {"transcript": text, **res}


@app.get("/admin")
def admin_page(): return FileResponse(ROOT / "static/admin.html")


@app.get("/screen")
def screen(): return FileResponse(ROOT / "static/screen.html")


@app.get("/")
def index(): return FileResponse(ROOT / "static/index.html")


app.mount("/", StaticFiles(directory=ROOT / "static"), name="static")
