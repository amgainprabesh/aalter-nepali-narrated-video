# Shipping an Aalter episode — thumbnail, metadata, disclaimer, music

The film is not the deliverable on its own. Every episode ships with a thumbnail that carries text, a
title, a description with real chapter timings, and optionally a disclaimer card at the head.

## Thumbnail

**The rule: it must carry text, in the loud YouTube idiom.** A calm title-only card gets rejected.
Shape that works, verified twice with the user:

```
<short setup line, white, ~64 px>
<ONE giant word in red, 132–150 px, heavy dark-red drop shadow>
<short payoff line, white, ~60 px>
<gold chip: the promise, e.g. ७ नियम · एउटा गल्ती>
```

- Pull the hook from the script's own claim, never from imagination: `ठाउँ गलत भए — प्रणामको फल
  शून्य`, `४ बजे उठेर / गल्ती / फोन हेर्नु`.
- **Two variants, two hook types**: a fear hook and a promise hook (`दिन जित्न / १२ मिनेट /
  पर्याप्त छ`). Fear wins CTR in this niche; the promise one is the safer brand image.
- Keeps the film's look: extract 2–3 frames from the finished render and pass them to `image_generate`
  as `reference_image_urls` (style references only), asking for the subject on one third of the frame
  with the other two thirds dark and empty for the title.
- **Lay the text out in HTML at exactly 1280×720 and screenshot it** — `browser_exec` with
  `Emulation.setDeviceMetricsOverride(width=1280, height=720)`, then `capture_screenshot`, then
  convert to JPEG (`ffmpeg -q:v 2`; keep it under ~2 MB). Never ffmpeg `drawtext` for Devanagari.
- Give every line its own band: `line-height: 1.2`+ and 14–16 px margins, red reduced to ~132 px. The
  failure the user notices is the red word's drop shadow touching the line beneath it — verify that gap
  on the render before shipping.
- Keep `thumb/*.html` and the base PNG in the project so a word change is a 5-second re-shot.

## Title and description

- Title: the question + the promise, e.g. `घरको मन्दिर कता राख्ने? शिवले पार्वतीलाई भनेका ७ नियम र
  एउटा गल्ती`. Offer one alternate.
- Description: hook paragraph → `के सिक्नुहुनेछ` numbered list → `अध्याय:` timestamps → disclaimer
  paragraph → comment prompt + subscribe → hashtags.
- **Chapters come from the rendered timing, not the script's intent** — read the SRT or the beat
  windows and round to the second. YouTube needs the first stamp at `0:00`.
- When asked for English, translate the whole description and keep the disclaimer verbatim in English.

## Disclaimer card

```bash
# 1 s card at the picture's size/frame rate, silence underneath
ffmpeg -y -loop 1 -i disclaimer.png -f lavfi -i anullsrc=r=48000:cl=stereo -t 1 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=24,format=yuv420p" \
  -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest card.mp4
# then concat, picture streams copied
printf "file '%s'\nfile '%s'\n" "$(cygpath -w "$PWD")/card.mp4" "$(cygpath -w "$PWD")/out/film.mp4" > cat.txt
ffmpeg -y -f concat -safe 0 -i cat.txt -c copy -movflags +faststart out/film-final.mp4
```

- Hold **1 second**, not five — the user corrected this once already.
- **The user's own PNG beats a card you rendered.** When they send a disclaimer image, drop it in as
  `disclaimer.png`, delete the old `disclaimer.html` so no stale source of truth remains, and rebuild
  the card. Card text is never re-typed from a transcription — the pixels are the contract.
- Verify **inside the concatenated film**, not on `card.mp4`: extract the frame at t=0.5 s with
  `ffmpeg -ss 0.5 -frames:v 1` and read it with `vision_analyze`. A card can be right and still be
  left out of the concat.
- Verify: card window silent (~−91 dB) and speech starting exactly at the card's end; shift any SRT by
  the card duration.
- A `1672×941` PNG pads cleanly to 1080p with black bars; do not stretch it.

## Music

- Ask for the track if none was sent; `--music none` for silence.
- Bed sits ~−33 dB under the voice (`BED = 0.09`), voice normalised to −16 LUFS, 3 s fade in/out.
- **A guide's "−20 dB" is a level, not a `volume` value.** Measure the supplied track first:
  `ffmpeg -ss 30 -t 10 -i music.wav -af volumedetect -f null -` gives its `mean_volume`; a stock track
  around −14.8 dB needs `volume=0.4` for −20 dB, and `volume=0.1` would bury it at −35 dB. Set `BED`
  from that measurement and say the resulting level in the report, rather than repeating the guide's
  number back to the user.
- **A supplied short track must be crossfaded before it is handed to the build.** The build loops
  with `-stream_loop -1`, which hard-cuts at every join; a stock clip that ends loud (28 s clips
  end ~−11 dB) clicks audibly there, and a 10-minute film needs ~21 of those joins.
  Build the bed once, then pass it:

  ```bash
  # through the terminal tool; stdlib + ffmpeg only
  python "<skill>/scripts/music_bed.py" music-source.m4a 600 music.wav
  ```

  It chains N copies with 0.9 s `acrossfade` and trims to the picture length, so the build sees a
  bed of the right duration and never loops it. Check the join survived: `volumedetect` on 0.9 s
  windows either side of the first join should ramp down, not drop to silence.
- Keep the source next to the project (`music-source.m4a`) and the derived bed as `music.wav`;
  `script.json`'s `music` field points at `music.wav`, so a re-run needs no flag.
- An `.mp3`/`.m4a` supplied by the user may carry cover art — `ffprobe` then lists an extra `mjpeg`
  stream. It is harmless as long as the mix maps video from the picture and only `[a]` from the bed.
