# Prompt packs

Every tool in this repo was built by talking to Claude Code, not by writing code by hand.
These packs are the reverse-engineered build conversations: the exact sequence of prompts,
in order, that gets you from an empty folder to each working skill.

I'm not an engineer. What I bring is the brief, the quality bar and the refusal to call
something done before it's checked. The packs are written so a colleague with the same
background can do the same thing.

| Pack | What it rebuilds | What it teaches |
|---|---|---|
| [`01-deckforge.md`](01-deckforge.md) | [`html-to-ppt/`](../html-to-ppt/) | Writing a quality standard before the build, then making the tool grade itself against it |
| [`02-quietscribe.md`](02-quietscribe.md) | [`transcript/`](../transcript/) + [`transcript-to-summary/`](../transcript-to-summary/) | Splitting a job into a deterministic stage and an AI stage, and keeping data local |
| [`03-truetag.md`](03-truetag.md) | [`product-history/`](../product-history/) | Designing a tool that refuses to answer when the evidence is thin |
| [`04-colleague-starter-pack.md`](04-colleague-starter-pack.md) | Nothing - it's for people, not code | Role-based prompts, a safe-use guide and a job aid for colleagues starting with an AI assistant |

## How to use a build pack

1. Open an empty folder in Claude Code.
2. Paste the prompts one at a time, in order. Don't merge them. Each one ends at a point you can check.
3. Run the check at the end of each step before moving on. If it fails, say what failed and ask for a fix - don't restart.
4. Your version won't match mine line for line. It should pass the same checks.

## The pattern behind all three builds

- **Brief first.** Who is it for, what does "good" look like, what must it never do.
- **Standard before code.** A written, numbered quality bar the output is graded against.
- **Deterministic spine, AI on top.** Scripts do the parts that must be repeatable; the model does judgment.
- **Verify, don't trust.** Every build ends with an independent check of the saved output.
- **Say the limits out loud.** Every README has a known-limitations section. Keep it honest.
