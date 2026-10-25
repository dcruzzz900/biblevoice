"""Optional connector to API.Bible (https://scripture.api.bible) for licensed versions (NIV, ESV, NKJV, NASB, AMP, MSG...).
Online: missing chapters are fetched on demand and cached in bible.db, so they then work offline.
Setup:  export API_BIBLE_KEY=your_key
  python api_bible.py list                         # find Bible ids available to your key
  python api_bible.py add NIV <bibleId> "New International Version"
  python api_bible.py download NIV                 # optional: cache whole Bible while online
"""
import os, re, sys, json, urllib.request

KEY = os.getenv("API_BIBLE_KEY")
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO "
        "OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS "
        "1PE 2PE 1JN 2JN 3JN JUD REV").split()


def call(path):
    req = urllib.request.Request("https://api.scripture.api.bible/v1" + path, headers={"api-key": KEY or ""})
    return json.load(urllib.request.urlopen(req, timeout=15))["data"]


def cache_chapter(c, code, api_id, book, ch):
    if c.execute("SELECT 1 FROM verses WHERE version=? AND book=? AND chapter=? LIMIT 1", (code, book, ch)).fetchone():
        return
    d = call(f"/bibles/{api_id}/chapters/{USFM[book-1]}.{ch}?content-type=text&include-verse-numbers=true"
             "&include-titles=false&include-notes=false")
    parts = re.split(r"\[(\d+)\]", d["content"])  # "[1] In the beginning..." -> verse rows
    for n, t in zip(parts[1::2], parts[2::2]):
        text = " ".join(t.split())
        cur = c.execute("INSERT INTO verses(version,book,chapter,verse,text) VALUES(?,?,?,?,?)", (code, book, ch, int(n), text))
        c.execute("INSERT INTO vfts(rowid,text) VALUES(?,?)", (cur.lastrowid, text))
    c.commit()


if __name__ == "__main__":
    from main import db
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if not KEY: sys.exit("Set API_BIBLE_KEY first.")
    if cmd == "list":
        for b in call("/bibles?language=" + (sys.argv[2] if len(sys.argv) > 2 else "eng")): print(b["id"], b.get("abbreviation"), "-", b["name"])
    elif cmd == "add":
        c = db(); c.execute("INSERT OR REPLACE INTO versions(code,name,api_id) VALUES(?,?,?)", sys.argv[2:5]); c.commit(); print("Added", sys.argv[2])
    elif cmd == "download":
        c = db(); api_id = c.execute("SELECT api_id FROM versions WHERE code=?", (sys.argv[2],)).fetchone()["api_id"]
        for i, u in enumerate(USFM, 1):
            for ch in call(f"/bibles/{api_id}/books/{u}/chapters"):
                if ch["number"].isdigit(): cache_chapter(c, sys.argv[2], api_id, i, int(ch["number"]))
            print("cached", u)
