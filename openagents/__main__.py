"""Allow `python -m openagents ...` to invoke the CLI."""

from openagents.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
