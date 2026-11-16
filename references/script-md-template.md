# script.md — template

Fill this in and hand it over as the single file for phase 1. Keep the four parts in this order and
keep the JSON block last — phase 2 reads only that block.

---

# <Nepali title>

**Length:** <5 or 10> minutes · **Shots:** <N> · **Language:** Nepali narration

## What this film is

One paragraph: the question it answers, the single visual idea, and the one image the viewer should
remember afterwards.

## How to direct it

Four to eight short rules, no technical settings:

- One idea per shot; the shot changes on the narration line, about every 3 seconds.
- Two worlds, one grade — <cold divine world> vs <warm human world>, never mixed in a frame.
- Camera is patient: one slow movement per shot, no whips.
- Hands and lamps are the close-ups; faces for feeling, not information.
- Recurring people, identical costume in every shot.
- The turn of the film is <the tension moment>; hold it longer than is comfortable, then release.
- End on scale, not a close-up.

## Beat by beat

The narration column **is** the voiceover script — it does not need to be requested separately.
Each row is one shot, ~3 s, 5–8 words.

| # | Narration (Nepali) | Shot direction |
|---|---|---|
| 01 | …। | … |
| 02 | …। | … |

## Script data (phase 2 reads this block)

```json
{
  "title": "…",
  "slug": "kebab-case-slug",
  "length_s": 300,
  "voice": {"engine": "eleven", "name": "Chris"},
  "music": null,
  "lines": [
    {"id": 1, "text": "Shiva भन्नुहुन्छ — नेपाली वाक्य।", "visual": "English shot direction"},
    {"id": 2, "text": "नेपाली वाक्य।", "visual": "English shot direction"}
  ]
}
```

Note the `Shiva` spelling: hard Sanskrit proper nouns go in Latin script inside the Devanagari line,
because the TTS reads `शिव` as “Siv”.
