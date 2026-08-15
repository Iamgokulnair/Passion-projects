#!/usr/bin/env bash
# product-history — setup (macOS / Linux)
#
# There is nothing to install. This skill is pure Python stdlib by design:
# no venv, no pip, no lockfile, no build step. Setup is therefore a preflight
# check of the two things it actually depends on, both from agent-reach.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

ok=0
fail=0
say()  { printf "  %-34s %s\n" "$1" "$2"; }
pass() { say "$1" "OK — $2"; ok=$((ok+1)); }
bad()  { say "$1" "FAIL — $2"; fail=$((fail+1)); }

echo
echo "  product-history — preflight"
echo "  ────────────────────────────────────────────────────────────"

# 1. Python 3.9+
if command -v python3 >/dev/null 2>&1; then
  PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
  if python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)'; then
    pass "python3" "$PYV"
  else
    bad "python3" "$PYV found, need 3.9+"
  fi
else
  bad "python3" "not on PATH"
fi

# 2. Jina Reader — agent-reach's 'web' channel. The fetch layer.
if curl -sS -m 25 -H "x-timeout: 10" -o /dev/null -w "%{http_code}" \
     "https://r.jina.ai/https://example.com" 2>/dev/null | grep -q "^200$"; then
  pass "agent-reach web (Jina Reader)" "reachable"
else
  bad "agent-reach web (Jina Reader)" "unreachable — the fetch layer is down"
fi

# 3. Exa via mcporter — agent-reach's 'search' channel. The resolver.
if command -v mcporter >/dev/null 2>&1; then
  pass "mcporter" "$(command -v mcporter)"
  if command -v agent-reach >/dev/null 2>&1; then
    EXA="$(agent-reach doctor --json 2>/dev/null \
           | python3 -c 'import sys,json;print(json.load(sys.stdin).get("exa_search",{}).get("status","unknown"))' 2>/dev/null || echo unknown)"
    [ "$EXA" = "ok" ] && pass "agent-reach search (Exa)" "ok" \
                      || bad  "agent-reach search (Exa)" "status=$EXA"
  else
    say "agent-reach CLI" "not found — skipping doctor check"
  fi
else
  bad "mcporter" "not on PATH — product name lookup will not work"
fi

# 4. Self-test against the captured fixtures. Proves the parsers still hold.
echo
echo "  running golden tests…"
if python3 tests/test_golden.py; then
  ok=$((ok+1))
else
  fail=$((fail+1))
fi

echo "  ────────────────────────────────────────────────────────────"
if [ "$fail" -eq 0 ]; then
  echo "  Ready. Try:"
  echo "    python3 scripts/ph.py \"<amazon.in URL or product name>\""
  echo
  exit 0
fi
echo "  $fail check(s) failed — see SETUP.md."
echo
exit 1
