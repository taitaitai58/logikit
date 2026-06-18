"""Enable ``python -m logikit`` to run the unified CLI (see logikit.cli)."""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())
