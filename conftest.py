"""
Root-level pytest configuration.

pytest.ini's `pythonpath = .` already puts the repository root on sys.path
for modern pytest. This file is kept as a defensive fallback (e.g. for
older pytest versions or unusual invocation setups) so `import backend`
reliably works no matter where pytest is launched from, as long as it's
launched from (or below) the repository root.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
