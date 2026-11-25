"""`python -m opendither` opens the desktop app; with arguments it runs the CLI."""
import sys

if len(sys.argv) > 1:
    from .cli import main
else:
    from .gui import main

sys.exit(main())
