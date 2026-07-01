"""Single ship gate: run plan verification steps 1–4 and fail on hygiene issues."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from path_setup import BACKEND_DIR as _BACKEND_DIR_STR

BACKEND_DIR = Path(_BACKEND_DIR_STR)
PROJECT_ROOT = BACKEND_DIR.parent
SCRATCH = Path(
    os.environ.get(
        "GOAL_SCRATCH_DIR",
        r"C:\Users\joshl\AppData\Local\Temp\grok-goal-4d376d7f037a\implementer",
    )
)
SCRATCH.mkdir(parents=True, exist_ok=True)

ENV = {
    **os.environ,
    "PYTEST_PGDATA_DIR": str(SCRATCH / "pytest_pgdata"),
}

# Code-only deliverables for this hygiene + verification round (no data dirs).
SHIPPED_CODE_FILES: tuple[str, ...] = (
    "tests/postgres_bootstrap.py",
    "tests/e2e/walkthrough_http.py",
    "tests/e2e/test_full_api_walkthrough.py",
    "api/routes/calls.py",
    "scripts/verify_goal.py",
    ".gitignore",
)

REQUIRED_MARKERS: dict[str, str] = {
    "tests/postgres_bootstrap.py": "owlbell-pytest-pgdata",
    "tests/e2e/walkthrough_http.py": "access_url",
    "tests/e2e/test_full_api_walkthrough.py": "seed_calls_for_tenant must seed",
    "api/routes/calls.py": "recordings_by_call",
    "scripts/verify_goal.py": "VERIFY_GOAL_OK",
    ".gitignore": ".pytest_pgdata_test/",
}

REQUIRED_SECURITY = (
    "SECURITY_EXERCISE_OK",
    "analytics_tenant_a_calls=3",
    "stripe_portal_cross_tenant=403",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_shipped_manifest() -> list[str]:
    """Write changed_files_manifest.txt (code paths only) and verify on disk."""
    lines: list[str] = []
    missing: list[str] = []
    for rel in SHIPPED_CODE_FILES:
        path = BACKEND_DIR / rel
        if not path.is_file():
            missing.append(rel)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        marker = REQUIRED_MARKERS.get(rel)
        if marker and marker not in text:
            missing.append(f"{rel} (missing marker {marker!r})")
            continue
        lines.append(f"{rel} sha256={_file_sha256(path)}")
    manifest = SCRATCH / "changed_files_manifest.txt"
    manifest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return missing


def _check_pytest_output(output: str, step: str) -> None:
    if re.search(r"\b[1-9]\d* failed\b", output):
        raise SystemExit(f"{step}: pytest reported failures")
    if re.search(r"\b[1-9]\d* skipped\b", output):
        raise SystemExit(f"{step}: pytest reported skips")
    if "warnings summary" in output.lower():
        section = output.lower().split("warnings summary", 1)[1]
        if re.search(r"\.py:\d+:", section):
            raise SystemExit(f"{step}: pytest warnings present")
    if "pytestunraisable" in output.lower():
        raise SystemExit(f"{step}: unraisable exceptions present")


def _run(cmd: list[str], log_name: str, *, append: bool = False) -> tuple[int, str]:
    log_path = SCRATCH / log_name
    print(f"\n=== {log_name} ===", flush=True)
    proc = subprocess.run(
        cmd,
        cwd=str(BACKEND_DIR),
        env=ENV,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    mode = "a" if append and log_path.exists() else "w"
    with log_path.open(mode, encoding="utf-8") as fh:
        if append and mode == "a":
            fh.write("\n\n--- next run ---\n\n")
        fh.write(output)
    print(output, end="", flush=True)
    with (SCRATCH / "verify_goal.log").open("a", encoding="utf-8") as master:
        master.write(f"\n\n=== {log_name} (exit {proc.returncode}) ===\n")
        master.write(output)
    return proc.returncode, output


def _ensure_editable_install() -> None:
    """Install package in editable mode so imports work without PYTHONPATH."""
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps", "--ignore-requires-python", "-q"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "pip install -e . failed:\n" + (proc.stdout + proc.stderr)
        )


def main() -> None:
    (SCRATCH / "verify_goal.log").write_text("", encoding="utf-8")
    failures: list[str] = []

    try:
        _ensure_editable_install()
    except SystemExit as exc:
        failures.append(str(exc))

    missing = _write_shipped_manifest()
    if missing:
        failures.append(f"shipped files missing or incomplete: {', '.join(missing)}")

    launch_script = (
        "from backend.app_factory import create_app\n"
        "app = create_app(env='testing')\n"
        "paths = [getattr(r, 'path', '') for r in app.routes]\n"
        "print('LAUNCH_OK')\n"
        "print('HAS_ANALYTICS:', any('/analytics' in p for p in paths))\n"
        "print('HAS_AGENCY:', any('/agency' in p for p in paths))\n"
        "print('HAS_TOOLS:', any('/agent/tools' in p for p in paths))\n"
        "print('ROUTE_COUNT:', len(paths))\n"
    )
    for i in (1, 2):
        code, out = _run(
            [sys.executable, "-c", launch_script],
            "app_factory_launch.log",
            append=(i > 1),
        )
        if code != 0 or "LAUNCH_OK" not in out:
            failures.append(f"launch run {i} failed (exit {code})")

    code, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-r",
            "w",
            "--tb=line",
            "--no-cov",
            "-k",
            "test_full_api_walkthrough or (auth or tenant or middleware)",
            "tests/e2e/",
        ],
        "walkthrough_and_auth_tests.log",
    )
    if code != 0:
        failures.append(f"walkthrough+auth pytest exit {code}")
    else:
        try:
            _check_pytest_output(out, "walkthrough+auth")
        except SystemExit as exc:
            failures.append(str(exc))

    code, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-r",
            "w",
            "--tb=short",
            "--no-cov",
            "-k",
            "analytics or agency or agent_tools or billing or business",
            "--maxfail=5",
        ],
        "p0_p1_route_tests.log",
    )
    if code != 0:
        failures.append(f"p0/p1 pytest exit {code}")
    else:
        try:
            _check_pytest_output(out, "p0/p1")
        except SystemExit as exc:
            failures.append(str(exc))

    code, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-r",
            "w",
            "--tb=line",
            "--no-cov",
            "tests/e2e/test_full_api_walkthrough.py",
        ],
        "walkthrough_full.log",
    )
    if code != 0:
        failures.append(f"full walkthrough pytest exit {code}")
    else:
        try:
            _check_pytest_output(out, "full walkthrough")
        except SystemExit as exc:
            failures.append(str(exc))

    code, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-r",
            "w",
            "--tb=short",
            "--no-cov",
            "tests/test_security_hardening.py",
        ],
        "security_tests.log",
    )
    if code != 0:
        failures.append(f"security hardening pytest exit {code}")
    else:
        try:
            _check_pytest_output(out, "security hardening")
        except SystemExit as exc:
            failures.append(str(exc))

    code, out = _run(
        [sys.executable, "scripts/security_exercise.py"],
        "security_exercise.log",
    )
    if code != 0:
        failures.append(f"security_exercise exit {code}")
    for marker in REQUIRED_SECURITY:
        if marker not in out:
            failures.append(f"security_exercise missing marker: {marker}")

    if failures:
        print("\nVERIFY_GOAL_FAILED", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)
        raise SystemExit(1)

    print("\nVERIFY_GOAL_OK", flush=True)
    print(f"Evidence directory: {SCRATCH}", flush=True)
    print(f"Shipped manifest: {SCRATCH / 'changed_files_manifest.txt'}", flush=True)


if __name__ == "__main__":
    main()