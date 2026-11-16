"""Aalter build: silent picture + script.json -> finished film with a Nepali voiceover.

What it does, in order:
  1. probe the picture, detect its shot cuts
  2. map each script line to its own shot (line i -> shot i), or partition the shots over the
     lines when the counts differ
  3. speak every line separately (exact sync: no splitting, no ASR)
  4. fit each line into its shot window — time-stretch only if the line is too long, hard stop
     at the next cut so a line can never overlap the next shot
  5. build the music bed, mix, copy the picture untouched
  6. verify: speech present in every window, durations, tempo-clamped lines

Usage:
  python aalter_build.py <project_dir> [--video video.mp4] [--music music.m4a|none]
                         [--engine eleven|gemini|edge] [--voice Brian] [--slug name]

<project_dir>/script.json is the only required input:
  {"title": ..., "slug": ..., "voice": {"engine": "eleven", "name": "Brian"},
   "music": null, "lines": [{"id": 1, "text": "...", "visual": "..."}]}
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave

SR = 48000
FPS = 30
MAX_TEMPO = 1.45        # a short list line can take 1.4× without sounding rushed
BED = 0.09              # music bed ≈ −33 dB under the voice
CUT_THRESHOLD = 0.10    # ffmpeg scene score for a shot change (dark, similar shots score low)
BEAT_S = 3.0            # the picture is generated on a fixed beat; a cut is only where a beat starts
HERE = os.path.dirname(os.path.abspath(__file__))
EL_KEY = (os.path.join(os.environ["LOCALAPPDATA"], "hermes", ".elevenlabs_key") if os.name == "nt"
          else os.path.expanduser("~/.config/hermes/.elevenlabs_key"))
ELEVEN_IDS = {"Brian": "nPczCjzI2devNBz1zQrb", "Bill": "pqHfZKP75CvOlQylNhV4",
              "George": "JBFqnCBsd6RMkjVDRZzb", "Daniel": "onwK4e9ZLuTAKqWW03F9",
              "Chris": "iP95p4xoKVk53GoZ742B", "Eric": "cjVigY5qzO86Huf0OWal",
              "Adam": "pNInz6obpgDQGcFmaJgB", "Roger": "CwhRBWXzGAHq8TQ4Fs17",
              "Charlie": "IKne3meq5aSn9XLyUdCD", "Liam": "TX3LPaxmHKxFdv7VOQHJ"}
VS = {"stability": 0.62, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True}
GEMINI_MODELS = ["gemini-3.8-flash-lite-tts", "gemini-2.5-pro-preview-tts",
                 "gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview",
                 "gemini-3.8-flash-tts"]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(cmd)[:300]}\n{r.stderr[-1200:]}")
    return r


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", p]).stdout.strip())


def streams(p):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,width,height,r_frame_rate", "-of", "json", p]).stdout
    return json.loads(out).get("streams", [])


def detect_cuts(video, total):
    """Shot boundaries from the picture itself: [0, ...cuts..., total]."""
    stderr = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vf",
                             f"select='gt(scene,{CUT_THRESHOLD})',showinfo", "-an", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
    cuts = sorted(float(x) for x in re.findall(r"pts_time:([0-9.]+)", stderr))
    bounds = [0.0] + [c for c in cuts if 0.2 < c < total - 0.2] + [total]
    return bounds


def to_beats(shots, beat=BEAT_S):
    """Split every detected shot into whole beats of ~beat seconds.

    AI-generated pictures change every few seconds and scene detection misses the weaker cuts, so
    the cut list is not the rhythm. A 6 s hold is two beats; a 2.9 s shot is one.
    """
    out = []
    for a, b in shots:
        n = max(1, round((b - a) / beat))
        step = (b - a) / n
        out += [(a + i * step, a + (i + 1) * step) for i in range(n)]
    return out


def reconcile(shots, n):
    """Make the shot count equal the line count: merge the two shortest neighbours, or split the
    longest shot. Scene detection always misses or invents a cut or two, and this makes that
    harmless instead of shifting every later line onto the wrong shot."""
    shots = list(shots)
    while len(shots) > n:
        i = min(range(len(shots) - 1),
                key=lambda k: (shots[k][1] - shots[k][0]) + (shots[k + 1][1] - shots[k + 1][0]))
        shots[i:i + 2] = [(shots[i][0], shots[i + 1][1])]
    while len(shots) < n:
        i = max(range(len(shots)), key=lambda k: shots[k][1] - shots[k][0])
        a, b = shots[i]
        m = (a + b) / 2
        shots[i:i + 1] = [(a, m), (m, b)]
    return shots


def score(windows, lines):
    """How bad a mapping is: wrong-sized windows, plus the lines that would have to be sped up."""
    bad = 0.0
    for (lo, hi), line in zip(windows, lines):
        win = max(0.1, hi - lo)
        want = max(0.1, len(line["text"].split()) / 1.9)     # Nepali pace, words/s
        bad += abs(win - want) + 6 * max(0.0, want / win - MAX_TEMPO)
    return bad


def partition(bounds, lines, total):
    """Map every line to a contiguous run of shots and pick the cheaper of two mappings:

      * 1:1 — line i on shot i, after reconciling detection noise in the shot count;
      * partition — a DP that gives each line a word-proportional run of shots.

    For a 3 s-per-shot picture 1:1 wins; for a picture whose shots vary wildly, the DP wins.
    """
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    n_s, n_l = len(shots), len(lines)
    # The picture was generated one beat per line, so if the beat count is close, line i belongs on
    # beat i — that alignment is what makes the visual change land on the line. Only when the counts
    # disagree badly does the word-proportional DP take over.
    beats = to_beats(shots)
    if abs(len(beats) - n_l) <= max(4, n_l // 8):
        rec = reconcile(beats, n_l)
        return rec, f"1:1 on {len(beats)} beats ({n_s} cuts) -> {n_l} lines"
    cands = []
    # Fine-grained alternative: every cut plus a 1 s grid, so a line can be given its fair share of
    # a long shot or kept whole inside a short one.
    grid = sorted(set([round(x, 3) for x in bounds] +
                      [round(x * 1.0, 3) for x in range(0, int(total) + 1)]))
    slices = [(grid[i], grid[i + 1]) for i in range(len(grid) - 1)
              if grid[i + 1] - grid[i] > 0.2]
    n_k = len(slices)
    if n_k >= n_l:
        words = [max(1, len(l["text"].split())) for l in lines]
        want = [total * w / sum(words) for w in words]
        INF = float("inf")
        cost = [[INF] * (n_k + 1) for _ in range(n_l + 1)]
        back = [[0] * (n_k + 1) for _ in range(n_l + 1)]
        cost[0][0] = 0.0
        for i in range(1, n_l + 1):
            for k in range(i, n_k - (n_l - i) + 1):
                for j in range(i - 1, k):
                    if cost[i - 1][j] == INF:
                        continue
                    c = cost[i - 1][j] + abs((slices[k - 1][1] - slices[j][0]) - want[i - 1])
                    if c < cost[i][k]:
                        cost[i][k], back[i][k] = c, j
        groups, k = [], n_k
        for i in range(n_l, 0, -1):
            j = back[i][k]
            groups.append((j, k))
            k = j
        groups.reverse()
        dp = [(slices[j][0], slices[k - 1][1]) for j, k in groups]
        cands.append((score(dp, lines), dp, f"{n_l} lines fitted to {n_s} shots (word-proportional)"))
    if not cands:
        edges, acc = [0.0], 0.0
        words = [max(1, len(l["text"].split())) for l in lines]
        for w in [total * max(1, len(l["text"].split())) / sum(words) for l in lines][:-1]:
            acc += w
            edges.append(acc)
        edges.append(total)
        return [(edges[i], edges[i + 1]) for i in range(n_l)], f"{n_s} shots < {n_l} lines (proportional)"
    _, best, how = min(cands, key=lambda c: c[0])
    return best, how


def pcm(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                        "-f", "s16le", "-"], capture_output=True)
    if r.returncode:
        sys.exit(f"decode failed: {path}\n{r.stderr.decode()[-800:]}")
    return r.stdout


def tts_eleven(text, out, voice):
    key = open(EL_KEY).read().strip()
    vid = ELEVEN_IDS.get(voice, voice)
    mp3 = out.replace(".wav", ".mp3")
    for model in ("eleven_v4", "eleven_v3", "eleven_multilingual_v2"):
        body = {"text": text, "model_id": model,
                "voice_settings": VS}
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            open(mp3, "wb").write(urllib.request.urlopen(req, timeout=180).read())
            run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                 "-c:a", "pcm_s16le", out])
            os.remove(mp3)
            return model
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:160]
            print(f"      {model}: HTTP {e.code} {msg}", flush=True)
            if e.code == 401:
                sys.exit(f"ElevenLabs rejected the key (401) — check {EL_KEY}")
    sys.exit(f"ElevenLabs failed for: {text[:40]}…")


def tts_gemini(text, out, voice):
    sys.path.insert(0, HERE)
    import gemini_tts  # noqa: E402  (lives beside this script)
    for model in GEMINI_MODELS:
        try:
            gemini_tts.synth(text, voice, out, model=model, retries=1)
            return model
        except SystemExit as e:
            print(f"      {model} out of quota ({str(e)[:50]})", flush=True)
    sys.exit("every Gemini TTS model is out of free quota — rerun after the daily reset")


def tts_edge(text, out, voice):
    import asyncio
    import edge_tts
    mp3 = out.replace(".wav", ".mp3")
    asyncio.run(edge_tts.Communicate(text, voice or "ne-NP-SagarNeural", rate="-10%").save(mp3))
    run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
         "-c:a", "pcm_s16le", out])
    os.remove(mp3)
    return "edge"


TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,areverse")


def trim(src, workdir):
    """Cut the dead air TTS puts before and after the words.

    Without this every line carries 0.2–0.6 s of padding, which is what forces the long lines to
    be sped up; trimming them usually removes the need for any tempo change at all.
    """
    out = os.path.join(workdir, "_trim.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", TRIM,
         "-ac", "1", "-ar", str(SR), out])
    return out


def synth(line, engine, voice, cache):
    """One cached wav per line, keyed by engine+voice+a hash of the text."""
    import hashlib
    h = hashlib.sha1(line["text"].encode()).hexdigest()[:8]
    safe = re.sub(r"[^A-Za-z0-9]+", "-", voice or "voice")[:20]
    out = os.path.join(cache, f"line_{line['id']:03d}_{safe}_{h}.wav")
    if os.path.exists(out):
        return out
    print(f"    {line['id']:03d} tts…", flush=True)
    if engine == "eleven":
        tts_eleven(line["text"], out, voice)
        time.sleep(1)
    elif engine == "gemini":
        tts_gemini(line["text"], out, voice)
        time.sleep(3)
    else:
        tts_edge(line["text"], out, voice)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--video", default="video.mp4")
    ap.add_argument("--music", default=None)
    ap.add_argument("--engine", default=None)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--slug", default=None)
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    story = json.load(open(os.path.join(proj, "script.json"), encoding="utf-8"))
    lines = story["lines"]
    video = a.video if os.path.isabs(a.video) else os.path.join(proj, a.video)
    if not os.path.exists(video):
        sys.exit(f"picture not found: {video}")
    engine = (a.engine or story.get("voice", {}).get("engine") or "eleven").lower()
    voice = a.voice or story.get("voice", {}).get("name") or {
        "eleven": "Brian", "gemini": "Alnilam", "edge": "ne-NP-SagarNeural"}[engine]
    slug = a.slug or story.get("slug") or "film"
    music = a.music if a.music is not None else story.get("music")
    global VS   # a sync guide may name stability/similarity/style; default keeps the house delivery
    vs = story.get("voice_settings") or {}
    VS = {"stability": vs.get("stability", 0.62), "similarity_boost": vs.get("similarity_boost", 0.75),
          "style": vs.get("style", 0.2), "use_speaker_boost": vs.get("use_speaker_boost", True)}
    if music and music != "none" and not os.path.isabs(music):
        music = os.path.join(proj, music)
    if music == "none":
        music = None

    total = dur(video)
    cache = os.path.join(proj, ".aalter_cache", engine)
    os.makedirs(cache, exist_ok=True)
    print(f"picture {total:.2f}s · {len(lines)} lines · {engine}/{voice}", flush=True)

    bounds = detect_cuts(video, total)
    if all("start" in l and "end" in l for l in lines):
        # A sync guide already carries one exact window per line — trust it over any guess.
        windows = [(float(l["start"]), float(l["end"])) for l in lines]
        how = f"guide timestamps ({len(bounds) - 1} cuts)"
    else:
        windows, how = partition(bounds, lines, total)
    print(f"shots: {len(bounds) - 1} ({how})", flush=True)

    # ---- voice ----------------
    buf = bytearray(int(total * SR) * 2)
    over = []
    for i, line in enumerate(lines):
        lo, hi = windows[i]
        win = hi - lo
        src = trim(synth(line, engine, voice, cache), cache)
        data = pcm(src)
        have = len(data) / 2 / SR
        tempo = 1.0
        if have > win:
            tempo = min(have / win, MAX_TEMPO)
            if have / win > MAX_TEMPO:
                over.append((line["id"], round(have / win, 2), round(have, 2), round(win, 2)))
            tmp = os.path.join(cache, "_tempo.wav")
            run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter:a", f"atempo={tempo:.4f}",
                 "-ac", "1", "-ar", str(SR), tmp])
            data = pcm(tmp)
            os.remove(tmp)
        nxt = windows[i + 1][0] if i + 1 < len(windows) else total
        limit = int(min(len(data) / 2, (nxt - lo - 0.04) * SR))     # never overlap the next shot
        chunk = data[:max(0, limit) * 2]
        off = int(lo * SR) * 2
        buf[off:off + len(chunk)] = chunk
        print(f"  {line['id']:03d} {have:5.2f}s / {win:5.2f}s  tempo {tempo:4.2f}", flush=True)

    nar = os.path.join(proj, "narration.wav")
    with wave.open(nar, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(bytes(buf))

    # ---- mix ------------------
    out_dir = os.path.join(proj, "out")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{slug}.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", nar]
    if music and os.path.exists(music):
        if dur(music) < total - 0.5:
            cmd += ["-stream_loop", "-1", "-i", music]
        else:
            cmd += ["-i", music]
        fc = ("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[nar];"
              f"[2:a]volume={BED},afade=t=in:d=3,afade=t=out:st={total - 3:.2f}:d=3[bg];"
              "[nar][bg]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]")
    else:
        fc = "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.9[a]"
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", str(SR),
            "-movflags", "+faststart", "-shortest", out]
    run(cmd)

    # ---- verify --------------  (RMS per window, straight off the narration we just wrote)
    with wave.open(nar) as w:
        raw = w.readframes(w.getnframes())
    import array
    import math
    samples = array.array("h")
    samples.frombytes(raw)
    weak = []
    step = int(0.25 * SR)          # loudest quarter-second inside the window: a natural pause is fine,
    for i, line in enumerate(lines):   # a window with no speech at all is the bug worth reporting
        lo, hi = windows[i]
        a0, a1 = int(lo * SR), int(min(hi, total) * SR)
        best = -999.0
        for p0 in range(a0, max(a0 + 1, a1 - step), step):
            seg = samples[p0:min(p0 + step, a1)]
            if not seg:
                continue
            rms = (sum(float(x) * x for x in seg) / len(seg)) ** 0.5
            best = max(best, 20 * math.log10(max(rms / 32768.0, 1e-9)))
        if best < -40:
            weak.append((line["id"], round(best, 1)))

    report = [f"out: {out}", f"duration: {dur(out):.2f}s (picture {total:.2f}s)",
              f"lines: {len(lines)} · shots: {len(bounds) - 1} ({how})",
              f"weak/silent windows: {weak if weak else 'none'}",
              f"tempo-clamped (audible): {over if over else 'none'}"]
    open(os.path.join(proj, "build-report.txt"), "w", encoding="utf-8").write("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
