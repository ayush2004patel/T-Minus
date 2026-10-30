# Code that must produce no findings.
import json
import importlib

try:
    import imp  # guarded: the except clause catches ImportError
except ImportError:
    imp = None

import cgi  # tminus: ignore[v16-removed-python-stdlib]
