"""Shared test setup: put scripts/ on the import path.

The project keeps small readable scripts under scripts/ rather than a package.
Tests import those modules directly, so the directory goes on sys.path once
here.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
