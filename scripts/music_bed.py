#!/usr/bin/env python3
"""Loop a short music track into a seamless bed of an exact length.

  python music_bed.py <track> <seconds> <out.wav> [--xfade 0.9] [--db 0]

Why: the aalter build loops a too-short bed with `-stream_loop -1`, which hard-cuts at every
join. A supplied track that ends loud (most 28-30 s stock clips do) clicks there. This chains
copies of the track with `acrossfade`, then trims to the picture length.
"""
import math, subprocess, sys, json


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                          "-show_entries", "stream=sample_rate", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    return float(j["format"]["duration"]), int(j["streams"][0]["sample_rate"])


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        sys.exit(__doc__)
    track, seconds, out = a[0], float(a[1]), a[2]
    xf = float(a[a.index("--xfade") + 1]) if "--xfade" in a else 0.9
    dur, sr = probe(track)
    # n copies joined by (n-1) crossfades must still cover `seconds`
    n = max(2, math.ceil((seconds + xf) / (dur - xf)) + 1)
    ins, parts = [], []
    for _ in range(n):
        ins += ["-i", track]
    for k in range(n - 1):
        src = "[0:a]" if k == 0 else f"[a{k}]"
        parts.append(f"{src}[{k + 1}:a]acrossfade=d={xf}:c1=tri:c2=tri[a{k + 1}]")
    parts.append(f"[a{n - 1}]atrim=0:{seconds},asetpts=N/SR/TB[m]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(parts),
                    "-map", "[m]", "-ac", "2", "-ar", str(sr), "-c:a", "pcm_s16le", out], check=True)
    print(f"{out}: {probe(out)[0]:.2f}s from {n} x {dur:.2f}s laps ({xf}s crossfades)")


if __name__ == "__main__":
    main()
