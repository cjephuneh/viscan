"""Previous name of the model server. Runs scripts/model_server.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.model_server import main

if __name__ == "__main__":
    main()
