"""A distinct exploratory pipeline; never admits jobs to primary protected run."""
from outcome_poc.transfer_runtime import main

if __name__ == '__main__':
    raise SystemExit(main())
