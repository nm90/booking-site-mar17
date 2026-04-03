"""critical-before-request: skip booking auto-complete on /health and static."""


def test_health_does_not_run_transition_completed(app, monkeypatch):
    calls = []

    def track():
        calls.append(1)

    monkeypatch.setattr("backend.app.Booking.transition_completed", track)

    with app.test_client() as client:
        client.get("/health")
    assert calls == []


def test_static_does_not_run_transition_completed(app, monkeypatch):
    calls = []

    def track():
        calls.append(1)

    monkeypatch.setattr("backend.app.Booking.transition_completed", track)

    with app.test_client() as client:
        client.get("/static/css/main.css")
    assert calls == []


def test_app_routes_still_run_transition_completed(app, monkeypatch):
    calls = []

    def track():
        calls.append(1)

    monkeypatch.setattr("backend.app.Booking.transition_completed", track)

    with app.test_client() as client:
        client.get("/", follow_redirects=False)
    assert len(calls) == 1
