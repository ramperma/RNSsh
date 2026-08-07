"""Allow ``python -m rnssh``."""

from rnssh.app import main

if __name__ == "__main__":
    raise SystemExit(main())
