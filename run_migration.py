"""Run Alembic migration using Railway's environment variables."""
import subprocess
import sys

cmd = [
    sys.executable, "-m", "alembic",
    "-c", "backend/alembic.ini",
    "upgrade", "head"
]

result = subprocess.run(cmd, capture_output=True, text=True, cwd="C:\\Users\\joshl\\Downloads\\Business\\project")
print(result.stdout)
if result.returncode != 0:
    print(f"STDERR: {result.stderr}")
    print(f"Return code: {result.returncode}")
    sys.exit(result.returncode)
