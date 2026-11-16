# ElevenLabs — voices, gates, and the sample flow

All calls take the key from `%LOCALAPPDATA%\hermes\.elevenlabs_key` as an `xi-api-key` header.

## Which voices exist for Nepali

`GET /v1/shared-voices?language=ne` returns exactly three, which is the whole Nepali library:

| name | id | gender | usage (1y chars) |
|---|---|---|---|
| Ashok Pokhrel — Educational | `dn3M2FqG5VIRePAJqGHz` | male | 340k |
| Sarita — Nepali | `ljCTqT1biPnI7ZjS5gyi` | female | 5.3M |
| Kaanchi — Expressive | `BTUIboFmihb87sfmikzP` | female | 10.0M |

Hindi male voices the Nepali/Hindi mythology channels lean on:
`Prashant` `j7yQHuKNC1hdt1LBPAks` (7.2M), `Natraj` `7A62eQ9DpEHxK2EfhpmO` (documentary host, 1.2M).

## The plan gate

`GET /v1/user/subscription` is the only source of truth: `tier`, `character_limit`, `character_count`.
A key with 10 000 fresh credits still reports `tier: free`, and on free-tier pricing one Nepali
character is one credit — a 10-minute Nepali script (~11 600 chars, 1 837 words) is more than a free
month outright. Quote the shortfall in characters and in dollars (~$0.08 per 1k chars on v4) and let
the user choose between topping up and a different voice; never spend a partial budget on a script
that cannot finish. Before rendering, also sum the script's own text (`sum(len(l['text']))`) — a guide
that promises 3 000 characters can carry 11 000.

## The model must actually have the language

Check `GET /v1/models` and read each model's `languages` for `language_id == 'ne'`.
`eleven_multilingual_v2` — the model guides name for "Multilingual v2" scripts — does **not** list
Nepali; `eleven_v4` and `eleven_v3` do. The voice id is independent of the model, so a requested voice
(Chris) renders fine on v4 even when the guide named v2.

**Measured pace for planning:** Chris on v4 reads Nepali at ~1.87 words/s (11.8 chars/s), which is the
only number that matters for deciding whether a script fits a picture.

Library voices returned `402 {"detail":{"type":"payment_required","code":"paid_plan_required",
"message":"Free users cannot use library voices via the API"}}` on every model tried
(`eleven_v3`, `eleven_multilingual_v2`), even after `POST /v1/voices/add/{public_owner_id}/{voice_id}`
succeeded and the voice appeared in `/v1/voices`. Adding a library voice to a free account is not
permission to render with it.

So on a free plan the renderable set is the 21 stock voices only. Public `preview_url` fields from
`shared-voices` **are** downloadable without a plan — use those to let the user hear a library voice
before deciding to upgrade, but never promise a full render from them.

## Stock voices used so far

| name | id | character |
|---|---|---|
| Chris | `iP95p4xoKVk53GoZ742B` | charming, down-to-earth — **current default** |
| Brian | `nPczCjzI2devNBz1zQrb` | deep, resonant, comforting |
| Daniel | `onwK4e9ZLuTAKqWW03F9` | steady broadcaster |
| George | `JBFqnCBsd6RMkjVDRZzb` | warm storyteller (British) |
| Bill | `pqHfZKP75CvOlQylNhV4` | wise, mature, balanced |
| Eric | `cjVigY5qzO86Huf0OWal` | smooth, trustworthy |
| Adam | `pNInz6obpgDQGcFmaJgB` | dominant, firm |

## The sample flow the user expects

1. Budget first: `GET /v1/user/subscription` → `character_limit - character_count`. A 5-minute
   Nepali script is ~3 000 characters; free tier is 10 000 **per month**, so a full render plus one
   round of samples is usually the entire budget.
2. Sample 3–5 voices on **one short hard line** (~40–60 chars) — the same text for every voice, and
   it must contain a proper noun and a `—` pause. Long samples waste the budget without telling the
   user more.
3. Send the mp3s as attachments with a one-line character note per voice, and ask for a single name
   back.
4. Only then render the script. Cache means a re-run costs no characters, so after the first full
   render, fixes are free — but a *different voice* is a fresh full spend.

## Request shape that works

```python
body = {"text": line, "model_id": "eleven_v4",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15}}
# POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128
```

`eleven_v4` first, then `eleven_v3`, then `eleven_multilingual_v2` — v4 is the only model that has
sounded acceptable for Nepali prosody. ~1 s between requests keeps the API quiet.

## Pronunciation: Latin for hard proper nouns

Devanagari `शिव` is read as “Siv” by every model tried. Written as `Shiva` inside an otherwise
Devanagari sentence it is correct — the user approved that by ear. Same trick for other mangled
Sanskrit names; keep the sentence Nepali and only the proper noun in Latin.
