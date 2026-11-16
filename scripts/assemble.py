#!/usr/bin/env python3
"""Mix a pre-built narration onto a pre-built picture (card + film) with a music bed.

Use this when the picture was assembled by hand — 1 s disclaimer card concatenated onto the film — and
the build's narration.wav already sits on that timeline. Unlike aalter_build.py's own mux (which takes
the bed's length), this one checks the inputs line up first and then verifies every line window in the
finished file, so a silent window or a missing card cannot be shipped unnoticed.

  python assemble.py                        # narration.wav, music.wav, silent.mp4 -> out/final.mp4
  python assemble.py --verify-only          # measure the bed level alone, do not mux

Edit the per-project constants at the top of main(). Bed level is MEASURED, not copied from a guide:
BED is chosen so the music's mean_volume lands on TARGET_DB under the voice.
"""
import array
import json
import math
import os
import subprocess
import sys
import wave

SR = 48000
TARGET_DB = -20.0        # what a guide asks for, as a level — not a `volume` value


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(cmd)[:200]}\n{r.stderr[-1500:]}")
    return r


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", p]).stdout.strip())


def frames(p):
    return int(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", p]).stdout.strip())


def mean_db(p, start=30, length=10):
    out = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-t", str(length), "-i", p,
               "-af", "volumedetect", "-f", "null", "-"]).stderr
    for line in out.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    sys.exit(f"no mean_volume for {p}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    verify_only = "--verify-only" in sys.argv
    # ---- per-project constants ----
    video = os.path.join(here, "silent.mp4")
    nar = os.path.join(here, "narration.wav")
    music = os.path.join(here, "music.wav")
    out = os.path.join(here, "out", "final.mp4")
    per_line = os.path.join(here, "script.json")
    total = dur(video)

    bed = round(10 ** (TARGET_DB / 20 - mean_db(music) / 20), 3)
    print(f"bed: music means {mean_db(music):.1f} dB -> volume={bed} for {TARGET_DB:.0f} dB")
    if verify_only:
        return

    for f in (video, nar, music, per_line):
        if not os.path.exists(f):
            sys.exit(f"missing input: {f}")
    with wave.open(nar) as w:
        nar_s = w.getnframes() / w.getframerate()
    n = frames(video)
    # a guide in seconds only stays in sync when every cut sits on a whole frame
    if n % 24:
        sys.exit(f"picture is {n} frames — not a whole number of 24 fps seconds")
    if abs(nar_s - total) > 0.05:
        sys.exit(f"narration {nar_s:.2f}s vs picture {total:.2f}s — rebuild the narration on this timeline")

    fc = ("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[vo];"
          f"[2:a]volume={bed},afade=t=in:st=0:d=1.5,afade=t=out:st={total - 3:.2f}:d=3[bgm];"
          "[vo][bgm]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", nar, "-i", music,
         "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", str(SR),
         "-movflags", "+faststart", out])

    # ---- verify: one decode, RMS per 0.5 s, then the loudest half-second of every line window ----
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-map", "0:a:0", "-ac", "1",
                          "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw)
    step = SR // 2
    blocks = []
    for i in range(0, len(a) - step, step):
        seg = a[i:i + step]
        rms = (sum(float(x) * x for x in seg) / len(seg)) ** 0.5
        blocks.append((i / SR, 20 * math.log10(max(rms / 32768.0, 1e-9))))

    def level(lo, hi):
        v = [d for t, d in blocks if lo <= t < hi]
        return max(v) if v else -99.0

    lines = json.load(open(per_line, encoding="utf-8"))["lines"]
    weak = []
    levels = []
    for line in lines:
        lv = level(line["start"], line["end"])
        levels.append(lv)
        if lv < -40:
            weak.append((line["id"], round(lv, 1)))
    levels.sort()
    report = [f"out: {out}", f"duration: {dur(out):.2f}s · frames: {frames(out)}",
              f"card window (0-1s): {level(0, 1):.1f} dB (music fade-in only)",
              f"speech start (1-2s): {level(1, 2):.1f} dB · tail: {level(total - 2, total):.1f} dB",
              f"line windows with no speech: {weak if weak else 'none'}",
              f"line levels min/median/max: {levels[0]:.1f} / {levels[len(levels) // 2]:.1f} / {levels[-1]:.1f} dB"]
    open(os.path.join(here, "assemble-report.txt"), "w", encoding="utf-8").write("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
