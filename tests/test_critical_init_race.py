"""critical-init-race: parallel app import must not double-seed an empty DB."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl-based lock is POSIX-only")
def test_parallel_import_single_seed(tmp_path):
    db_path = tmp_path / "parallel_init.db"
    secret = "x" * 40
    project_root = Path(__file__).resolve().parent.parent
    code = f"""import os, sys, importlib
os.environ["DATABASE_PATH"] = {str(db_path)!r}
os.environ["SECRET_KEY"] = {secret!r}
sys.path.insert(0, {str(project_root)!r})
import backend.database.connection as _c
importlib.reload(_c)
import backend.app  # noqa: F401 — triggers init_database
"""
    p1 = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    p2 = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    err1 = p1.communicate(timeout=120)[1].decode()
    err2 = p2.communicate(timeout=120)[1].decode()
    assert p1.returncode == 0, err1
    assert p2.returncode == 0, err2

    conn = sqlite3.connect(str(db_path))
    n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    assert n_users == 3
