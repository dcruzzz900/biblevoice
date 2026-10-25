"""Measure how well BibleVoice understands YOUR speakers (Nigerian accents, your microphones and speakers).
1. Record short clips (wav/mp3/m4a/webm): the pastor saying "turn to Romans chapter eight verse one", and also ordinary talk.
2. Put them in a folder with expected.csv:      file,expected
                                                pastor1.wav,Romans 8:1
                                                chat1.wav,NONE          (NONE = nothing should open)
3. python eval_audio.py recordings/  [--model=medium]  [--no-prompt]    (try different models / the Bible-name prompt and compare)"""
import csv, os, sys, time


def evaluate(rows, transcribe, parse):
    out = []
    for f, exp in rows:
        text = transcribe(f); got = parse(text, strict=True)
        want = None if exp.strip().upper() == "NONE" else parse(exp)
        out.append({"file": f, "heard": text, "ok": got == want, "got": got, "want": want})
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit(__doc__)
    import main as M
    from faster_whisper import WhisperModel
    folder, name = args[0], next((a[8:] for a in sys.argv if a.startswith("--model=")), M.MODEL_NAME)
    wm, prompt = WhisperModel(name, compute_type="int8"), (None if "--no-prompt" in sys.argv else M.PROMPT)

    def tr(f):
        segs, _ = wm.transcribe(os.path.join(folder, f), language=os.getenv("WHISPER_LANG", "en"), initial_prompt=prompt, vad_filter=True, beam_size=5)
        return " ".join(s.text for s in segs).strip()

    def fmt(p): return "nothing" if p is None else f"{M.BOOKS[p[0]-1]} {p[1]}" + (f":{p[2]}" + (f"-{p[3]}" if p[3] else "") if p[2] else "")
    rows = [(r["file"].strip(), r["expected"]) for r in csv.DictReader(open(os.path.join(folder, "expected.csv"), encoding="utf-8-sig"))]
    t0 = time.time(); res = evaluate(rows, tr, M.parse)
    for r in res: print(("  ✓ " if r["ok"] else "  ✗ ") + r["file"] + f"\n      heard: {r['heard']!r}" + ("" if r["ok"] else f"\n      expected {fmt(r['want'])}   understood {fmt(r['got'])}"))
    n = sum(r["ok"] for r in res)
    print(f"\n{n}/{len(res)} correct · model '{name}' · {'no prompt' if not prompt else 'Bible-name prompt'} · {time.time()-t0:.0f}s")
    if n < 0.9 * len(res): print("Tip: try --model=medium, a closer microphone, or tell me which clips fail so I can tune the parser.")
