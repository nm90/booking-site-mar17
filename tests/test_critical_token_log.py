"""critical-token-log: reset flow must not write token or full URL to logs."""

import logging

from backend.models.user import User


def test_forgot_password_does_not_log_reset_url(app, monkeypatch):
    sent = []

    def fake_send(email, reset_url):
        sent.append((email, reset_url))

    monkeypatch.setattr(
        "backend.controllers.auth_controller.send_password_reset", fake_send
    )
    monkeypatch.setattr(
        User,
        "generate_reset_token",
        staticmethod(lambda _email: "SECRET-TOKEN-VALUE"),
    )

    log = logging.getLogger("backend.controllers.auth_controller")
    records = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r.getMessage())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        with app.test_client() as c:
            c.post(
                "/auth/forgot-password",
                data={"email": "anyone@example.com"},
                follow_redirects=False,
            )
    finally:
        log.removeHandler(handler)

    assert sent and "SECRET-TOKEN-VALUE" in sent[0][1]
    combined = " ".join(records)
    assert "SECRET-TOKEN-VALUE" not in combined
    assert "reset-password" not in combined.lower()
