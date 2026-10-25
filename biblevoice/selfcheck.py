"""Pre-service health check.   python selfcheck.py            (quick)
                              python selfcheck.py --download (online, once: fetches the speech model)
                              python selfcheck.py --whisper  (proves the speech model works with NO internet)"""
import importlib, os, sys
bad = 0


def chk(good, msg, fix=""):
    global bad
    print(("  ✓ " if good else "  ✗ ") + msg + ("" if good or not fix else "\n      → " + fix)); bad += not good


print("BibleVoice health check")
chk(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "Install Python 3.10 or newer")
for mod, pip in [("fastapi", "fastapi"), ("uvicorn", "uvicorn[standard]"), ("multipart", "python-multipart"), ("faster_whisper", "faster-whisper"), ("cryptography", "cryptography")]:
    try: importlib.import_module(mod); chk(True, f"{pip} installed")
    except Exception:
        if os.getenv("LIGHT") == "1" and mod in ("faster_whisper", "cryptography"): print(f"  · {pip} not installed (fine in light mode)")
        else: chk(False, f"{pip} missing", "pip install -r requirements.txt")
try: import main as M
except Exception as e: sys.exit(f"\n  ✗ Cannot load the app ({e}). Fix the items above first.")
db = M.db(); vers = db.execute("SELECT code,lang FROM versions").fetchall()
chk(bool(vers), "A Bible is installed", 'python import_bible.py KJV "King James Version" kjv.csv --default')
for v in vers:
    n, b = db.execute("SELECT COUNT(*),COUNT(DISTINCT book) FROM verses WHERE version=?", (v["code"],)).fetchone()
    chk(b == 66, f"{v['code']} ({v['lang']}): {n} verses, {b}/66 books", "Partial Bible. Import the complete file (fine if intended)")
for t, want in [("turn to John three sixteen", (43, 3, 16, None)), ("open your bible to Romans eight", (45, 8, None, None)), ("I met Mark yesterday", None)]:
    chk(M.parse(t, strict=True) == want, f"Understands: “{t}”", "Parser problem: please report this")
try: db.execute("SELECT count(*) FROM vfts WHERE vfts MATCH 'the'").fetchone(); chk(True, "Topic/name search works")
except Exception as e: chk(False, f"Search index problem ({e})", "Re-run import_bible.py for each Bible")
chk(db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone() is not None, "An admin account exists", "Open the app and create the first account (it becomes admin)")
chk(os.path.exists("cert.pem") or bool(os.getenv("DATA_DIR")) or os.getenv("LIGHT") == "1", "HTTPS certificate (phones need it for the microphone)", "python mkcert.py   (or use start.bat / start.sh)")
if os.getenv("LIGHT") == "1" or not M.HAVE_WHISPER: print("  · Light mode: phones do the speech recognition, so no speech model is needed here")
elif "--download" in sys.argv or "--whisper" in sys.argv:
    try:
        from faster_whisper import WhisperModel
        WhisperModel(M.MODEL_NAME, compute_type="int8", local_files_only="--download" not in sys.argv)
        chk(True, f"Speech model “{M.MODEL_NAME}” ready" + (" and works OFFLINE" if "--whisper" in sys.argv else ""))
    except Exception: chk(False, "Speech model not available offline", "Connect to the internet once and run: python selfcheck.py --download")
else: print("  · Speech model not checked (use --download once while online, then --whisper)")
print("\nAll good." if not bad else f"\n{bad} thing(s) to fix before Sunday.")
