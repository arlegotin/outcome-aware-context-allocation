"""Entrypoint imported only from the immutable reviewed execution snapshot."""
from pathlib import Path
import sys

from outcome_poc.protected import native_main

if __name__ == '__main__':
    native_main(Path(sys.argv[1]), int(sys.argv[2]))
