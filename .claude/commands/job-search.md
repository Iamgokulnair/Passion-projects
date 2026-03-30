---
description: >
  Scan the entire web for job matches, score against resume for ATS
  compatibility and recruiter confidence, and show only 90%+ matches.
  Covers LinkedIn, Naukri, Glassdoor, Foundit, Wellfound, TimesJobs,
  company career pages, and any other indexed source — no portal lock-in.
argument-hint: >
  Optional: [job title] [location] [--threshold=N] [--remote-only] [--max=N]
  Examples:
    /job-search
    /job-search "Head of Operations" Mumbai
    /job-search --threshold=85 --remote-only
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Write
  - TodoWrite
  - Bash
---

Read and execute the skill defined in:

  ~/Passion-projects/job-matcher/SKILL.md

That file contains the complete 10-step workflow. Follow every step in order,
exactly as written. Use TodoWrite to track each step.

Pass any arguments from this invocation into Step 1 (Parse Arguments) of
the SKILL.md workflow as overrides to the YAML defaults.

If the SKILL.md file cannot be read for any reason, stop and tell the user:
  "Could not load SKILL.md. Please ensure
  ~/Passion-projects/job-matcher/SKILL.md exists."
