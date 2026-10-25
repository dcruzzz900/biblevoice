"""Import a Bible. Format is auto-detected:
  .csv/.tsv  columns book,chapter,verse,text (any order/case; book = name or 1-66)
  .json      scrollmapper-style {"books":[{"name":..,"chapters":[{"verses":[{"text":..}]}]}]}  or  {"John":{"3":{"16":"text"}}}
  .zip/.usfm USFM from eBible.org etc. (a folder of .usfm files works too)
  .txt       one verse per line:  John 3:16 For God so loved the world...
Usage: python import_bible.py CODE "Name" file [--default] [--lang=yo|ha|ig|en] [--credit="text shown in the app"]"""
import csv, json, os, re, sys, difflib, zipfile
from main import db, db_init, NAMES

USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM "
        "HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
SKIP = re.compile(r"\\(?:id|ide|usfm|h|toc\d|mt\d?|ms\d?|mr|s\d?|sr|r|sp|d|cl|cd|b|rem|restore|periph|imt\d?|is\d?|ip|iot|io\d?)(?:\s|$)")


def usfm_text(text, out):
    """USFM (eBible.org, Bible Society exports...): \\id GEN, \\c 1, \\v 1 text, with footnotes/markers stripped."""
    text = re.sub(r"\\(f|fe|x)\s.*?\\\1\*", "", text, flags=re.S)                       # footnotes, cross-references
    text = re.sub(r"\\\+?w\s+([^|\\]*)(?:\|[^\\]*)?\\\+?w\*", r"\1", text)             # \w word|strong=".."\w*  ->  word
    book = ch = v = None; buf = []

    def emit():
        if book and ch and v and buf and " ".join(buf).strip(): out.append((book, ch, v, " ".join(" ".join(buf).split())))
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"\\id\s+(\w{3})", line)
        if m: emit(); book = USFM.index(m[1].upper()) + 1 if m[1].upper() in USFM else None; ch = v = None; buf = []; continue
        m = re.match(r"\\c\s+(\d+)", line)
        if m: emit(); ch, v, buf = int(m[1]), None, []; continue
        m = re.match(r"\\v\s+(\d+)(?:[-–,]\d+)?\s*(.*)", line)
        if m: emit(); v, buf = int(m[1]), [re.sub(r"\\\+?[a-z]+\d?\*?", "", m[2])]; continue
        if v and line and not SKIP.match(line): buf.append(re.sub(r"\\\+?[a-z]+\d?\*?", "", line))   # poetry / paragraph continuation
    emit()


def usfm_rows(path):
    out = []
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        for n in sorted(z.namelist()):
            if n.lower().endswith((".usfm", ".sfm")): usfm_text(z.read(n).decode("utf-8-sig"), out)
    elif os.path.isdir(path):
        for n in sorted(os.listdir(path)):
            if n.lower().endswith((".usfm", ".sfm")): usfm_text(open(os.path.join(path, n), encoding="utf-8-sig").read(), out)
    else: usfm_text(open(path, encoding="utf-8-sig").read(), out)
    return out


ROMAN = {"i": "1", "ii": "2", "iii": "3"}


def bookno(n):
    if str(n).strip().isdigit(): return int(n) if 1 <= int(n) <= 66 else None
    k = re.sub(r"^(the )?(book|gospel|epistle|letter) of( the)? ", "", str(n).lower().strip().rstrip("."))
    k = re.sub(r"^(\d)(st|nd|rd)? ", r"\1 ", re.sub(r"^(i{1,3})\.? ", lambda m: ROMAN[m[1]] + " ", k))
    if k in NAMES: return NAMES[k]
    m = difflib.get_close_matches(k, NAMES, 1, 0.8); return NAMES[m[0]] if m else None


def rows(path):
    if path.endswith((".zip", ".usfm", ".sfm")) or os.path.isdir(path): yield from usfm_rows(path); return
    if path.endswith(".json"):
        d = json.load(open(path, encoding="utf-8-sig"))
        d = d["books"] if isinstance(d, dict) and "books" in d else d
        if isinstance(d, list):
            for i, b in enumerate(d, 1):
                for ci, ch in enumerate(b["chapters"], 1):
                    vs = ch["verses"] if isinstance(ch, dict) else ch
                    for vi, v in enumerate(vs, 1):
                        yield (b.get("name") or b.get("book") or i, ch.get("chapter", ci) if isinstance(ch, dict) else ci,
                               v.get("verse", vi) if isinstance(v, dict) else vi, v["text"] if isinstance(v, dict) else v)
        else:
            for nm, chs in d.items():
                for cn, vs in chs.items():
                    for vn, t in vs.items(): yield nm, cn, vn, t
    elif path.endswith((".csv", ".tsv")):
        al = {"book": "book", "b": "book", "book_name": "book", "chapter": "chapter", "c": "chapter", "verse": "verse", "v": "verse", "text": "text", "t": "text", "verse_text": "text"}
        f = open(path, encoding="utf-8-sig", newline="")
        for row in csv.DictReader(f, delimiter="\t" if path.endswith(".tsv") else ","):
            x = {al.get(k.strip().lower(), k): v for k, v in row.items() if k}; yield x["book"], x["chapter"], x["verse"], x["text"]
    else:
        for line in open(path, encoding="utf-8-sig"):
            m = re.match(r"\s*((?:[1-3I]{1,3}\.?\s*)?[A-Za-z][A-Za-z ]+?)\s+(\d+):(\d+)\s+(.+)", line)
            if m: yield m.groups()


if __name__ == "__main__":
    code, name, path = sys.argv[1:4]; db_init(); c = db(); out, bad = [], set()
    for nm, ch, v, t in rows(path):
        b = bookno(nm)
        if not b: bad.add(str(nm)); continue
        out.append((code, b, int(ch), int(v), re.sub(r"<[^>]+>|\{[^}]*\}", "", str(t)).strip()))  # drop markup / Strong's tags
    if not out: sys.exit("No verses found. Check the file format (see the top of this script).")
    c.execute("DELETE FROM verses WHERE version=?", (code,)); c.executemany("INSERT INTO verses(version,book,chapter,verse,text) VALUES(?,?,?,?,?)", out)
    c.execute("INSERT INTO vfts(vfts) VALUES('rebuild')")
    c.execute("INSERT OR REPLACE INTO versions(code,name,is_default,lang,credit) VALUES(?,?,?,?,?)",
              (code, name, int("--default" in sys.argv), next((a[7:] for a in sys.argv if a.startswith("--lang=")), "en"),
               next((a[9:] for a in sys.argv if a.startswith("--credit=")), "")))
    c.commit(); nb = len({r[1] for r in out})
    print(f"Imported {len(out)} verses in {nb} books as {code}." + ("" if nb == 66 else f" Note: {nb}/66 books (partial Bible?)."))
    if bad: print("Skipped unknown book names:", ", ".join(sorted(bad)[:10]))
