"""
Root-level pytest configuration.

This inserts the `backend/` folder onto sys.path so that test files can do
plain imports like `from schemas import ...` or `from pipeline import ...`,
exactly the same way `main.py` does when you run uvicorn from inside the
`backend/` folder. This keeps import style consistent between "running the
app" and "running the tests" without needing to turn the project into a
formally installed package.
"""
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
