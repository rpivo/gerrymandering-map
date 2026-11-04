import sys
from pathlib import Path

# The tools are standalone scripts, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
