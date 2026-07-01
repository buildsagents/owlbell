# Gate-first verification for onboarding/intake (plan step 3).
# Usage: .\backend\scripts\run_plan_gates.ps1 [-ScratchDir <path>]
param(
    [string]$ScratchDir = $(if ($env:SCRATCH_DIR) { $env:SCRATCH_DIR } else { Join-Path $env:TEMP "grok-goal-implementer" })
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Venv = Join-Path $ProjectRoot ".venv"
$Log = Join-Path $ScratchDir "onboarding_tests.log"

New-Item -ItemType Directory -Force -Path $ScratchDir | Out-Null
Set-Content -Path $Log -Value "=== run_plan_gates.ps1 $(Get-Date -Format o) ==="

function Write-Log($Text) {
    Write-Host $Text
    Add-Content -Path $Log -Value $Text
}

if (-not (Test-Path $Venv)) {
    Write-Log "Creating venv at $Venv"
    py -3 -m venv $Venv
}

$Pip = Join-Path $Venv "Scripts\pip.exe"
$Python = Join-Path $Venv "Scripts\python.exe"

Write-Log "Installing gate requirements (minimal, Windows-safe)"
& $Pip install -q -r (Join-Path $ProjectRoot "backend\requirements-gates.txt")

$env:PYTHONPATH = $ProjectRoot
Set-Location $ProjectRoot

Write-Log "Running pytest -k 'onboarding or intake' --no-cov"
$GateTests = @(
    "backend/tests/test_onboarding_activation.py",
    "backend/tests/test_onboarding_intake.py",
    "backend/tests/test_onboarding_intake_contract.py",
    "backend/tests/test_onboarding_orchestrator.py",
    "backend/tests/test_onboarding_script_versions.py",
    "backend/tests/test_intake_service.py",
    "backend/tests/test_self_serve_pipeline.py"
)
& $Python -m pytest -q --tb=line -k "onboarding or intake or self_serve_pipeline" --no-cov -o "addopts=-ra --strict-markers --tb=line" @GateTests 2>&1 | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "pytest FAILED with exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

$PipelineLog = Join-Path $ScratchDir "pipeline_exercise.log"
Write-Log "python -c exercise execute_self_serve_activation (plan step 3)"
& $Python -c @"
from backend.domain.onboarding.self_serve_pipeline import execute_self_serve_activation
import json
payload = {
    'email': 'exercise@example.com',
    'businessName': 'Exercise Co',
    'selfServe': True,
    'forwardNumber': '(512) 555-0100',
    'voiceId': 'warm_professional',
    'crmProvider': 'jobber',
    'pricingTier': 'growth',
}
out = execute_self_serve_activation(payload)
assert out['activated'] is True
assert out['inbound_line'] != out['forward_line']
print(json.dumps({'ok': out['ok'], 'activated': out['activated'], 'inbound_line': out['inbound_line'], 'forward_line': out['forward_line'], 'provision_mode': out['provision_mode']}))
"@ 2>&1 | Tee-Object -FilePath $PipelineLog -Append | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "pipeline exercise FAILED with exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Log "Pipeline: test_execute_self_serve_activation_zero_mocks + test_intake_handler_patches_only_persist_intake"

Write-Log "run_plan_gates: PASS"
exit 0