#!/usr/bin/python3

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eiltn.cli import main

if __name__ == "__main__":
    sys.exit(main())
