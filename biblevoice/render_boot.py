"""Runs before the server on Render. Free instances start with an empty disk after every sleep, so this re-imports the Bibles listed in
bibles/manifest.json whenever the database has none. (With a persistent disk it only imports once.)"""
import json, subprocess, sys
from pathlib import Path
import main as M  # creates the tables

ROOT = Path(__file__).parent
man = ROOT / "bibles" / "manifest.json"
if not man.exists(): print("render_boot: no bibles/manifest.json, skipping Bible import"); sys.exit(0)
have = {r["code"] for r in M.db().execute("SELECT code FROM versions")}
for b in json.loads(man.read_text(encoding="utf-8")):
    if b["code"] in have: continue
    cmd = [sys.executable, str(ROOT / "import_bible.py"), b["code"], b["name"], str(ROOT / "bibles" / b["file"]), f"--lang={b.get('lang', 'en')}"]
    if b.get("credit"): cmd.append(f"--credit={b['credit']}")
    if b.get("default"): cmd.append("--default")
    print("render_boot: importing", b["code"], flush=True); subprocess.run(cmd, cwd=ROOT, check=False)
