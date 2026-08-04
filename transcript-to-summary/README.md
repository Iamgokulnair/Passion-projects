# transcript-to-summary

Stage 2 of the pipeline started by [`../transcript/`](../transcript/): takes a transcript
(`.txt`/`.md`/`.srt`/`.vtt`/`.json` — exactly what `/transcript` produces, or pasted text) and
turns it into a structured Markdown summary — key points, decisions, action items with
owners/dates, notable quotes, and a chapter outline.

## Platform support

Every platform. This skill has no Python code and no dependencies of its own — it's a prompt
template that runs entirely inside Claude Code. If you can run Claude Code, this works, on
whatever OS that is.

## Install

Part of the same repo as `/transcript` — see that folder's [README](../transcript/README.md)
for the full walkthrough (install Claude Code, clone, symlink both skill folders in). There's
nothing separate to set up here.

## Use

```
/transcript path/to/recording.mp4          # verbatim transcript
/transcript-to-summary path/to/output.txt  # -> structured summary
```

Or paste transcript text directly into a Claude Code conversation and ask for a summary — it
detects speaker labels automatically and won't invent quotes, owners, or dates that aren't
actually in the source transcript.
