import sys
from pathlib import Path

# Ensure the backend app package is importable
sys.path.insert(0, str(Path(__file__).parent))

# Ensure the ml package (publish CLI) is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
