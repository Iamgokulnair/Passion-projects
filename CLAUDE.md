# Claude Code — Gokul's Workspace

## Automatic job sweep at session start

**When this session opens, do this immediately — before the user says anything:**

Run the job sweep by following the `/job-sweep` command instructions in `.claude/commands/job-sweep.md`.

Present the results directly in the chat. Start with:
> **Good morning, Gokul. Here's your job sweep for [today's date].**

Then show the Sure Shot card and full qualified table as defined in the command file.

---

## Manual sweep

If the user types `/job-sweep` at any point, run the sweep again on demand.
