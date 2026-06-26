import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
from alembic.config import main
main(argv=["-c", "backend/alembic.ini", "upgrade", "head"])
