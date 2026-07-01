"""Direct security exercise — thin wrapper around tests.security_evidence."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from path_setup import ensure_import_paths

ensure_import_paths()

from tests.postgres_bootstrap import bootstrap_postgres
from tests.security_evidence import print_evidence, run_security_checks


def main() -> None:
    bootstrap_postgres()
    lines = asyncio.run(run_security_checks())
    print_evidence(lines)


if __name__ == "__main__":
    main()