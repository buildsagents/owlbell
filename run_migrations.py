import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from path_setup import ensure_import_paths

ensure_import_paths()
from alembic.config import main
main(argv=["-c", "backend/alembic.ini", "upgrade", "head"])
