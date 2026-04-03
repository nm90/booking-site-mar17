"""medium-proxyfix: optional ProxyFix when TRUST_PROXY_HEADERS is set."""

import subprocess
import sys
from pathlib import Path

import pytest


def _subprocess_check(code: str) -> None:
    root = str(Path(__file__).resolve().parent.parent)
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="subprocess + fcntl init same as Linux CI")
def test_proxy_fix_wraps_wsgi_when_trust_env(tmp_path):
    db = tmp_path / "probe.db"
    secret = "y" * 40
    root = str(Path(__file__).resolve().parent.parent)
    code = f"""
import os, sys, importlib
os.environ["DATABASE_PATH"] = {str(db)!r}
os.environ["SECRET_KEY"] = {secret!r}
os.environ["TRUST_PROXY_HEADERS"] = "1"
sys.path.insert(0, {root!r})
import backend.database.connection as c
importlib.reload(c)
import backend.app as m
from werkzeug.middleware.proxy_fix import ProxyFix
assert isinstance(m.app.wsgi_app, ProxyFix), type(m.app.wsgi_app)

@m.app.route("/__probe_scheme")
def __probe_scheme():
    from flask import request
    return request.scheme

with m.app.test_client() as c:
    r = c.get(
        "/__probe_scheme",
        headers={{"X-Forwarded-Proto": "https", "Host": "example.com"}},
    )
    assert r.data == b"https", r.data
print("ok")
"""
    _subprocess_check(code)


@pytest.mark.skipif(sys.platform == "win32", reason="subprocess POSIX init")
def test_no_proxy_fix_when_trust_env_unset(tmp_path):
    db = tmp_path / "probe2.db"
    secret = "z" * 40
    root = str(Path(__file__).resolve().parent.parent)
    code = f"""
import os, sys, importlib
os.environ["DATABASE_PATH"] = {str(db)!r}
os.environ["SECRET_KEY"] = {secret!r}
os.environ.pop("TRUST_PROXY_HEADERS", None)
sys.path.insert(0, {root!r})
import backend.database.connection as c
importlib.reload(c)
import backend.app as m
from werkzeug.middleware.proxy_fix import ProxyFix
assert not isinstance(m.app.wsgi_app, ProxyFix), type(m.app.wsgi_app)
print("ok")
"""
    _subprocess_check(code)
