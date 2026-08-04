---
name: transcript-to-summary
user-invocable: true
description: >-
  Turn an already-transcribed transcript into a structured Markdown summary — key points,
  decisions, action items with owners/dates, notable quotes, and a chapter outline. Use for
  "summarize this transcript", "give me the key points from this call", "turn this into
  meeting notes", "what were the action items", "who said what in this interview", "make me
  notes from this recording's transcript". Takes a transcript file (.txt/.md/.srt/.vtt/.json)
  or pasted transcript text as input — it does NOT transcribe audio or video itself; for a
  recording with no transcript yet, use `/transcript` (../transcript/SKILL.md) first and feed
  its output here. The two skills are a pipeline: `/transcript` (recording → verbatim text) →
  `/transcript-to-summary` (verbatim text → structured summary).
---

# transcript-to-summary

A transcript in → a structured summary out. Single pass, no transcription, no audio/video
handling — that boundary belongs entirely to the sibling `../transcript/` skill, which
deliberately produces verbatim-only output and explicitly excludes summarization. This skill
is the downstream step that skill was designed to hand off to.

## Input

Accepts any of:
- A file path to a transcript: `.txt` (timestamped lines), `.md` (speaker-turn prose),
  `.srt`/`.vtt` (subtitle format), or `.json` (`{segments: [{start, end, text, speaker}]}`) —
  these are exactly `/transcript`'s six output formats.
- Pasted transcript text directly in the conversation.

If the input is audio or video (not yet transcribed), say so and point to `/transcript` —
don't attempt to transcribe it yourself.

## Detecting speaker labels

Check whether the transcript has speaker attribution (`SPEAKER_00:` turns in the `.md`, a
`speaker` field in the `.json`, or similar). `/transcript`'s diarization is optional — it
degrades to a flat transcript when there's no Hugging Face token, so **don't assume speakers
exist**. Branch on what's actually in the file:

- **Speaker labels present** → attribute quotes and points to the specific speaker in the
  summary (`SPEAKER_00`, or a real name if the user has already told you the mapping).
- **No speaker labels** → produce the same summary structure without attribution. Don't
  invent speaker identities or guess who said what from context alone.

## Output structure

Always use this exact template, omitting a section only when the transcript genuinely has
nothing for it (say so in one line rather than silently dropping the heading):

```markdown
# Summary — <source name or topic>

## Key Points
- ...

## Decisions
- ...

## Action Items
- [Owner if stated] — task — [due date if stated]

## Notable Quotes
> "Verbatim quote" — Speaker (if known)

## Outline
- [00:00] Topic/chapter
- [00:00] Topic/chapter
```

Timestamps in the Outline come from the source transcript's own timing — only include them
if the input actually has timestamps (the `.txt`/`.srt`/`.vtt`/`.json` formats do; a
plain-pasted block of text may not).

## Fidelity rule

Every quote and every action item must trace back to something actually said in the
transcript — this is a summary of a real conversation, not a paraphrase that invents intent.
If an action item is implied but never explicitly assigned or dated, list it under Key Points
instead of Action Items rather than inventing an owner or date. The whole value of this skill
is that someone can trust the summary without re-reading the source; a single fabricated
quote or made-up deadline breaks that trust for the whole document.

## Output format

Markdown only, returned inline or saved alongside the source transcript as
`<name>.summary.md` if the user is working from a file. No other export format (no Word, no
Notion) — keep this skill a plain, fast, single-pass step; if a polished export is needed
later, that is a separate downstream task.
