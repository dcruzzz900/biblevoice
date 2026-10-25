"""How pastors really say references. Run: python tests/test_parser.py   (add your own lines as you find misses)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main as M

OPEN = [  # spoken phrase -> (book, chapter, verse1, verse2)
 ("turn to John three sixteen", ("John", 3, 16, None)),
 ("John chapter three verse sixteen", ("John", 3, 16, None)),
 ("the gospel according to St John chapter 3 verse 16", ("John", 3, 16, None)),
 ("Hebrews eleven verse one", ("Hebrews", 11, 1, None)),
 ("Hebrews eleven and verse one", ("Hebrews", 11, 1, None)),
 ("Philippians four thirteen", ("Philippians", 4, 13, None)),
 ("Second Timothy chapter three verses sixteen to seventeen", ("2 Timothy", 3, 16, 17)),
 ("Psalm one hundred and twenty one", ("Psalms", 121, None, None)),
 ("Psalm one hundred and nineteen verse one hundred and five", ("Psalms", 119, 105, None)),
 ("Romans eight, one", ("Romans", 8, 1, None)),
 ("Genesis chapter one, verse one", ("Genesis", 1, 1, None)),
 ("Isaiah fifty-three five", ("Isaiah", 53, 5, None)),
 ("Matthew twenty eight nineteen to twenty", ("Matthew", 28, 19, 20)),
 ("Acts two vs one", ("Acts", 2, 1, None)),
 ("Luke chapter fifteen from verse eleven", ("Luke", 15, 11, None)),
 ("John 3:16", ("John", 3, 16, None)),
 ("John 3:16-17", ("John", 3, 16, 17)),
 ("1 Corinthians 13 verses 4 to 7", ("1 Corinthians", 13, 4, 7)),
 ("first John chapter four verse eight", ("1 John", 4, 8, None)),
 ("Revelation twenty-two verse twenty-one", ("Revelation", 22, 21, None)),
 ("open your Bible to Ephesians chapter 6", ("Ephesians", 6, None, None)),
 ("Genesys chapter one verse one", ("Genesis", 1, 1, None)),
 ("the book of Romans", ("Romans", 1, None, None)),
]
IGNORE = ["Mark my words", "Job well done", "John is here today", "we are in acts of service", "James and John went home", "mark 3 times",
          "Ruth 2 people came", "good job 5 of them", "I met Mark yesterday", "what time is lunch", "God is good all the time"]
bad = 0
for text, want in OPEN:
    p = M.parse(text, strict=True); got = (M.BOOKS[p[0] - 1],) + p[1:] if p else None
    if got != want: bad += 1; print(f"  ✗ {text!r}\n      expected {want}  got {got}")
for text in IGNORE:
    p = M.parse(text, strict=True)
    if p: bad += 1; print(f"  ✗ {text!r} should be ignored but opened {M.BOOKS[p[0]-1]} {p[1:]}")
print(f"{len(OPEN)+len(IGNORE)-bad}/{len(OPEN)+len(IGNORE)} passed"); sys.exit(1 if bad else 0)
