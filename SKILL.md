---
name: aalter
description: Nepali narrated video — script.md then synced voiceover.
version: 0.1.0
author: Hermes
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [Video, Nepali, TTS, ElevenLabs, Sync, YouTube]
    related_skills: [faceless-shorts, media-use]
---

# Aalter — script.md, then a synced Nepali voiceover

Produces a narrated Nepali film in two turns: turn one writes `script.md` (narration + direction +
machine-readable lines), turn two takes the user's silent picture back and returns the finished film
with a per-line voiceover, music bed and verified sync. It does not generate the picture — the user
renders that from the shot directions — and it does not caption or burn subtitles. Needs `ffmpeg` on
PATH plus an ElevenLabs key; no other dependency beyond stdlib Python.

## When to Use

- “give me the script and prompt for the video”, “script.md”, “I'll tell you the length”
- “I have generated the video, here it is — add the voiceover”, “sync the audio”
- “redo the voiceover in a different voice”, “the pronunciation is wrong”
- “thumbnail”, “title and description”, “add the disclaimer at the start” for an episode already built

## Prerequisites

- `ffmpeg` + `ffprobe` on PATH (checked by every script in this skill).
- ElevenLabs key at `%LOCALAPPDATA%\hermes\.elevenlabs_key` — plain text, one line. Ask for it once if
  absent, save it there, never echo it into chat.
- Free tier is 10 000 characters per month and 5-minute scripts are ~3 000 — read the budget
  (`GET /v1/user/subscription`) before sampling and say the number to the user.
- Read the budget from the plan, never from the key's history: `GET /v1/user/subscription` →
  `character_limit - character_count`. That one call also tells you the tier (`free` = no commercial
  licence for renders) and nothing about whether a key has been topped up — a 10 000-credit key is
  still `tier: free` and still ~$0.08/1k chars for a paid render. Say the number and the tier to the user.
- A partial budget is not a small budget. The build speaks **every** line, so a 40 % shortfall fails
  halfway and still burns the characters. Quantify the whole script
  (`sum(len(text))` over `script.json`) and have the user decide before the first TTS call.
- Library voices (the famous Nepali ones) need a paid plan — see `references/elevenlabs-voices.md`.

## Fit the script to the picture before paying for it

A sync guide can be internally consistent and still be unfilmable: 1 837 Nepali words over a 600 s
picture is 3.06 words/s, while every Nepali voice measures **1.8–1.9 words/s**. Check the word count
against the picture *before* spending characters — cheaper to rewrite the script than to stretch a film.

If the script does not fit, these are the only honest options, and the user picks one:

| option | picture | voice | cost |
|---|---|---|---|
| stretch picture | `setpts * need/600`, re-encode | natural | free after the voice is cut |
| cut script text | untouched | natural | re-record the changed lines |
| speed the voice | untouched | 1.3× and up sounds rushed | free off `.aalter_cache/` |
| accept a longer film | stretched | natural, 0.35 s breath between lines | free |

- **Cache decides which option is cheap.** Different line *windows* reuse every clip (free); different
  line *text* is a fresh spend. Build windows from the real clip lengths when you arrive at a different
  picture length: `start_i = prev_end`, `end_i = start_i + clip_i + 0.35`.
- Stretch the footage, not a concat of clips: `-vf "setpts=(PTS-STARTPTS)*need/600" -r 24` on the whole
  picture keeps every cut where it was relative to the shot and only slows the motion (seen smooth at
  ×1.43 by eye). It is also expensive to encode — a 10-min 24 fps film to 17 min takes ~10 min CPU; run
  it with `background=true, notify=true`.
- **Frame alignment is part of sync.** A guide in seconds only lines the voice up if the concat keeps
  whole frames: `ffprobe -count_frames` on card+picture, and reject the build when the frame count is
  not `round(frames/24)*24 + card_frames`. The muxed file's duration then shows the last audio
  packet's tail (e.g. 1039.10 for a 1039.06 film) — a ~0.04 s label, not drift.

## How to Run

Phase 1 is authoring: `write_file` the finished `script.md` into `<project>/script.md` and stop.

Phase 2 is one command, invoked through the `terminal` tool:

```bash
python "C:/Users/<user>/AppData/Local/hermes/skills/creative/aalter/scripts/aalter_build.py" \
  <project_dir> --video video.mp4 --music music.m4a
```

It writes `out/<slug>.mp4` plus `build-report.txt`. Read the report before answering.

## Quick Reference

| item | value |
|---|---|
| build | `scripts/aalter_build.py <project> --video f --music f --engine eleven --voice Chris` |
| long build | run it with `terminal(background=true, notify=true)` — a 10-min mix exceeds a 180 s foreground call |
| free re-mix | `.aalter_cache/<engine>/` holding one clip per line means narration is free to rebuild (`-c:v copy`) |
| short music | `scripts/music_bed.py <track> <seconds> music.wav` before the build |
| lines for 5 min | ~100 (one line = one shot = ~3 s) |
| words for 5 min | ~515 at Nepali pace ~1.9 words/s — a guide with more words than this will not fit |
| voice | ElevenLabs `Chris` `iP95p4xoKVk53GoZ742B`, model `eleven_v4` |
| other stock voices | Brian, Daniel, George, Bill, Eric, Adam (ids in the build script) |
| tempo clamp | 1.45× max; delivery bar is **zero** clamped lines |
| music bed | `BED = 0.09` is −33 dB only on a track that means −24 dB; measure it (`volumedetect`) and set `BED = 10 ** (target_db/20 - track_mean_db/20)` |
| voice loudness | loudnorm `I=-16 TP=-1.5 LRA=11` |
| thumbnail | 1280×720 JPEG, text laid out in a browser |
| disclaimer card | 1 s hold, silent, `-c copy` concat; frame count of the concat must be whole pictures |
| mixing levels | `volume=0.1` is −20 dB, `0.4` is ≈−8 dB — a guide's "−20 dB" is not a `volume` value |

Load on demand with `skill_view(name="aalter", file_path=…)`:

| file | load it when |
|---|---|
| `references/script-md-template.md` | writing phase 1's `script.md` |
| `references/elevenlabs-voices.md` | choosing/sampling a voice, or a `402` appears |
| `references/thumbnail-and-shipping.md` | thumbnail, title/description, disclaimer card, music |
| `scripts/aalter_build.py` | the whole phase-2 build — invoke it, don't retype it |
| `scripts/music_bed.py` | the supplied track is shorter than the picture |
| `scripts/assemble.py` | mixing narration + bed onto an already-built picture (card + film), with per-window verification |

## Procedure

1. **Ask for the length** (5 or 10 minutes) if it was not given. Never invent it. Budget:
   `lines ≈ length_s / 3`, `words ≈ length_s × 1.9`.
2. **Write `script.md`** — one file, four parts, in this order, template in
   `references/script-md-template.md`:
   1. what the film is (title, length, shot count, the one visual idea);
   2. how to direct it — plain direction only, **no resolutions, fps, codecs, model names, file
      paths or negative-prompt lists**;
   3. `# | narration (Nepali) | shot direction` table, one row per shot, plus the explicit line that
      the narration column **is** the voiceover script (so the user need not ask for it separately);
   4. a fenced `json` block with `title`, `slug`, `length_s`, `voice`, `music`, `lines[]` — the only
      thing phase 2 reads.
   Structure that holds attention: 0–12 s cold open with a consequence → tease the payoff + “the
   mistake almost everyone makes” → god-and-consort dialogue frame → numbered points → hidden
   mistake → comment prompt + subscribe.
   Line rules: 5–8 Nepali words, ends on `।` or `?`, Devanagari digits (७ not 7), one shot per line.
3. **Hand over.** Do not generate audio in the same turn unless asked.
4. **When the silent video arrives**, put everything in one folder and extract the JSON block from
   `script.md` into `script.json` — that file is the build's only input. If the guide carries
   timestamps, carry `start`/`end` into every line.
5. **Settle the voice before rendering.** Send 3–5 mp3 samples of *one short hard line* (a proper
   noun + a `—` pause) from `samples/`, one note per voice, and wait for a single name back. Cache
   makes re-runs free, but a different voice is a fresh full character spend. `script.json` may carry
   the guide's own `voice_settings` (stability, similarity_boost, style, use_speaker_boost); the build
   honours those over its house 0.62/0.75/0.2, so copy a guide's numbers across instead of dropping them.
6. **Fix pronunciation by respelling, not by changing voice** — `शिव` is read “Siv”; write `Shiva`
   in Latin inside the Devanagari sentence. A/B it with a 30-character sample first.
7. **Build**, read `build-report.txt`, and only then answer. It maps line *i* to beat *i*, trims dead
   air off each clip, fits lines to their windows and mixes. For a 10-minute picture the mix alone
   runs past a foreground `terminal` call — launch it with `background=true, notify=true` and pick the
   work up when it exits, never by re-polling. The background session id does not survive into a later
   call; `process_manage(action='list')` finds it and `poll` only accepts a still-live one.
8. **Ship the episode**: thumbnail, title + description, optional 1 s disclaimer card — see
   `references/thumbnail-and-shipping.md`.
9. **Corrections on a shipped film are surgical.** A wrong music track, disclaimer or picture is fixed
   on its own: replace the file, rebuild only the derived asset (`scripts/music_bed.py`, `card.mp4`),
   re-run the build, re-concat. The TTS is free off `.aalter_cache/<engine>/` — count the cached clips
   against the lines before promising that, then verify the fix at t=0.5 s of the *concatenated* output.

## Pitfalls

- **Never substitute the voice the user chose** — not for quota, not for a `402`, not for speed. Stop
  and state the blocker, then offer the fallback as a question.
- **A sync guide with per-line `start`/`end` beats all guessing.** When the shot list came with timestamps,
  put `start`/`end` on every line in `script.json`; the build then uses those windows verbatim instead
  of `partition()`. Prove it first: `select='gt(scene,0.10)'` cut times must equal the guide's boundaries.
- **Cut detection is not the rhythm.** ffmpeg finds ~88 cuts for 100 shots on dark AI footage; split
  each shot into `round(duration / 3 s)` beats and map line i to beat i before trusting any cut list.
- **A short supplied bed needs crossfading, not `-stream_loop`.** The build loops a short track with a
  hard cut at every join; stock clips end loud, so a 10-minute film gets ~21 audible clicks. Run
  `scripts/music_bed.py` first (`references/thumbnail-and-shipping.md`).
- **A guide-timestamped script tiles the whole film** — consecutive lines have zero-length gaps — so
  there is no silence to measure the bed in. Prove the bed is present by re-running the build with the
  track swapped or by trusting `music.wav`'s own RMS; do not look for a gap that isn't there.
- **Verify the disclaimer on the final concat, at t=0.5 s**, with `vision_analyze` — never on the
  intermediate `card.mp4`, and never by trusting a transcription of the PNG.
- **ffmpeg `drawtext` mangles Devanagari** (`ख्न` → `ख्छ`). Burn Nepali text only via an HTML page
  screenshotted at 1280×720, never drawtext.
- **Verify burned-in text on a crop**: whole-frame reads misread conjuncts and digits (४ as ८).
- **Probe the loudest 0.25 s inside each window**, not one mid-point: a natural pause otherwise looks
  like silence and raises false alarms.
- **Zero clamped lines or it isn't done** — fix the script line or re-render at 1.45×, never ship the
  clipped take. A long list of clamped lines means the script does not fit the picture, not that the
  voice is slow: report the count and stop for a decision (see "Fit the script to the picture").
- **Never trust a guide's model name for a language.** `eleven_multilingual_v2` does not list Nepali at
  all; `eleven_v4` and `eleven_v3` do. Check `GET /v1/models` → each model's `languages` for
  `language_id == 'ne'` before rendering, whatever the script says.
- **Never judge audio from one sample.** `-ss`/`volumedetect` reads of the same half-second differ from a
  full-decode read, and a single compressed peak inside a quiet stretch reads −14 dB. Sweep the whole
  file once in Python (RMS per 0.5 s, then max per line window) and judge consistency — no window
  under −40 dB, levels within a few dB of each other — not one number.
- **A killed `assemble.py`/mux holds the output handle.** Kill the background verifier
  (`process_manage kill`) before renaming or deleting the output, or `mv` fails 'Device or resource
  busy' while the file otherwise looks finished.
- A subtitle sidecar from the generator (if present) beats cut detection — use its cue windows.
- Native tools on this host need `C:/…` paths, not `/c/…`.

## Verification

```bash
python -c "import json;t=json.load(open('<project>/script.json'));print(len(t['lines']),'lines')"
ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,channels,sample_rate \
  -of default=nw=1 <project>/out/<slug>.mp4
```

Pass conditions, all from `build-report.txt` and the probe above: duration equals the picture's,
an `aac` 48 kHz stereo track exists, `weak/silent windows: none`, `tempo-clamped: none`. Anything
else is a draft, not a delivery.
