# -*- coding: utf-8 -*-
"""Deprecated updater.

Use deploy_scf.py from this directory instead. The old script targeted the
ap-shanghai function and a C: drive zip, which can redeploy stale code.
"""

raise SystemExit(
    "update_and_test2.py is deprecated. Run: python rebuild_v4.py, then python deploy_scf.py"
)
