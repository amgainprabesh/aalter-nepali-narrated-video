# aalter — Nepali narrated video skill

A Hermes Agent skill that turns a **silent picture** into a finished **Nepali narrated film**
in two turns:

1. **Turn one** — write `script.md`: narration (Devanagari), shot-by-shot direction, and a
   machine-readable `json` block of lines.
2. **Turn two** — you hand back the silent video and it returns the film with a per-line
   voiceover, a music bed, and verified sync.

It does not generate the picture and it does not burn subtitles. It needs `ffmpeg` plus an
ElevenLabs key; everything else is stdlib Python.

## What's inside

| file | what it does |
|---|---|
| `SKILL.md` | the two-phase procedure, budgets, pitfalls, verification |
| `references/script-md-template.md` | the exact `script.md` shape (content + json block) |
| `references/elevenlabs-voices.md` | choosing/sampling a voice, paid-tier voice notes, 402 handling |
| `references/thumbnail-and-shipping.md` | thumbnail, title/description, disclaimer card, music bed |
| `scripts/aalter_build.py` | the phase-2 build: TTS, trim, fit-to-window, mix, report |
| `scripts/music_bed.py` | crossfade-loop a short track to the film length (no clicks) |
| `scripts/assemble.py` | mix narration + bed onto an already-built picture, per-window verification |

## Setup

### 1. Install the skill into Hermes

```bash
# Windows (git-bash)
mkdir -p ~/AppData/Local/hermes/skills/creative/aalter
cp -r SKILL.md references scripts ~/AppData/Local/hermes/skills/creative/aalter/

# macOS / Linux
mkdir -p ~/.config/hermes/skills/creative/aalter
cp -r SKILL.md references scripts ~/.config/hermes/skills/creative/aalter/
```

Start a new session and check `skills_list` shows `aalter`, or load it with
`skill_view(name="aalter")`.

### 2. Install the tools

```bash
ffmpeg -version    # required
ffprobe -version   # required
```

Nothing to pip install — the scripts use only the standard library.

### 3. Add your ElevenLabs key

Plain text, one line, no quotes, at:

```
Windows:      %LOCALAPPDATA%\hermes\.elevenlabs_key
macOS/Linux:  ~/.config/hermes/.elevenlabs_key
```

The skill never echoes the key into chat. Check the plan budget before rendering —
`GET /v1/user/subscription` gives `character_limit - character_count`. Free tier is
10 000 characters/month and a 5-minute script is ~3 000; that same call also reports the
tier (`free` = no commercial licence for renders). The build speaks **every** line, so a
partial budget fails halfway and still burns the characters.

### 4. First run

Ask for it in plain language:

- *"give me the script and prompt for a 5 minute Nepali video about X"* → you get `script.md`.
- *"I've generated the video, here it is — add the voiceover"* → put `script.md`'s json block
  into `script.json` next to `video.mp4`, then:

```bash
python "<skills>/creative/aalter/scripts/aalter_build.py" <project_dir> \
  --video video.mp4 --music music.m4a --engine eleven --voice Chris
```

It writes `out/<slug>.mp4` and `build-report.txt`. A 10-minute mix outruns a foreground
terminal call — run it in the background and read the report when it exits.

### 5. Know before you pay

A sync guide can be consistent and still unfilmable: every Nepali voice measures **1.8–1.9
words/s**, so 1 837 words does not fit a 600 s picture. Budget `lines ≈ length_s / 3` and
`words ≈ length_s × 1.9`, and check the word count against the picture before the first TTS
call. If it does not fit, the skill lists the only four honest options (stretch the picture,
cut text, speed the voice, accept a longer film) with their real costs.

Rebuilds are free off `.aalter_cache/<engine>/` — one clip per line — but a **different voice**
is a fresh full spend, so settle the voice on 3–5 short samples first.

### 6. Verify before shipping

Pass conditions, all from `build-report.txt` plus an `ffprobe`:

- duration equals the picture's
- an `aac` 48 kHz stereo track exists
- `weak/silent windows: none`
- `tempo-clamped: none` — zero clamped lines, or it is not done

## Requirements recap

- `ffmpeg` + `ffprobe` on PATH
- ElevenLabs key file as above, with enough credited characters for the whole script
- a silent picture and (optionally) a music track

## License

MIT. See `LICENSE`.
