# product-history — setup (Windows)
#
# Nothing to install: this skill is pure Python stdlib by design. Setup is a
# preflight check of the two agent-reach channels it depends on.
#
# NOTE: untested on Windows — no Windows machine was available when this
# shipped. The macOS path (scripts/setup.sh) is the verified one. If this
# script misbehaves, the checks below are all runnable by hand.

$ErrorActionPreference = "Continue"
$SkillDir = Split-Path -Parent $PSScriptRoot
Set-Location $SkillDir

$ok = 0
$bad = 0
function Pass($n, $d) { "{0,-34} OK — {1}" -f $n, $d | Write-Host; $script:ok++ }
function Fail($n, $d) { "{0,-34} FAIL — {1}" -f $n, $d | Write-Host; $script:bad++ }

Write-Host ""
Write-Host "  product-history — preflight"
Write-Host "  ------------------------------------------------------------"

# 1. Python 3.9+
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if ($py) {
    $v = & $py.Source -c "import sys;print('%d.%d'%sys.version_info[:2])"
    & $py.Source -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)"
    if ($LASTEXITCODE -eq 0) { Pass "python" $v } else { Fail "python" "$v found, need 3.9+" }
} else {
    Fail "python" "not on PATH"
}

# 2. Jina Reader — agent-reach 'web' channel
try {
    $r = Invoke-WebRequest -Uri "https://r.jina.ai/https://example.com" `
                           -Headers @{ "x-timeout" = "10" } `
                           -TimeoutSec 25 -UseBasicParsing
    if ($r.StatusCode -eq 200) { Pass "agent-reach web (Jina Reader)" "reachable" }
    else { Fail "agent-reach web (Jina Reader)" "HTTP $($r.StatusCode)" }
} catch {
    Fail "agent-reach web (Jina Reader)" "unreachable — the fetch layer is down"
}

# 3. Exa via mcporter — agent-reach 'search' channel
if (Get-Command mcporter -ErrorAction SilentlyContinue) {
    Pass "mcporter" "found"
} else {
    Fail "mcporter" "not on PATH — product name lookup will not work"
}

# 4. Golden tests
Write-Host ""
Write-Host "  running golden tests..."
& $py.Source tests\test_golden.py
if ($LASTEXITCODE -eq 0) { $ok++ } else { $bad++ }

Write-Host "  ------------------------------------------------------------"
if ($bad -eq 0) {
    Write-Host "  Ready. Try:"
    Write-Host "    python scripts\ph.py `"<amazon.in URL or product name>`""
    Write-Host ""
    exit 0
}
Write-Host "  $bad check(s) failed — see SETUP.md."
Write-Host ""
exit 1
