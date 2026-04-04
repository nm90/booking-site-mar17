"""Tests for Brevo transactional email transport."""

import json
from io import BytesIO
from unittest.mock import patch

import pytest

from backend.services import email as email_mod
from backend.services.email import _brevo_sender_from_config, _send


class _FakeResponse:
    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{}'


@pytest.mark.parametrize(
    'config,expected',
    [
        (
            {'MAIL_DEFAULT_SENDER': 'a@b.com', 'BREVO_SENDER_NAME': 'Brand'},
            {'email': 'a@b.com', 'name': 'Brand'},
        ),
        (
            {'MAIL_DEFAULT_SENDER': 'a@b.com', 'BREVO_SENDER_NAME': ''},
            {'email': 'a@b.com'},
        ),
        (
            {'MAIL_DEFAULT_SENDER': ('Human', 'human@b.com'), 'BREVO_SENDER_NAME': 'Ignored'},
            {'email': 'human@b.com', 'name': 'Human'},
        ),
    ],
)
def test_brevo_sender_from_config(config, expected):
    assert _brevo_sender_from_config(config) == expected


def test_brevo_sender_empty_email():
    assert _brevo_sender_from_config({'MAIL_DEFAULT_SENDER': '   '}) is None
    assert _brevo_sender_from_config({'MAIL_DEFAULT_SENDER': ('', '')}) is None


def test_send_brevo_builds_request_and_succeeds(app):
    app.config['BREVO_API_KEY'] = 'secret-api-key'
    app.config['MAIL_DEFAULT_SENDER'] = 'from@example.com'
    app.config['BREVO_SENDER_NAME'] = 'Casita'

    captured = {}

    def fake_urlopen(request, timeout=30):
        captured['request'] = request
        captured['timeout'] = timeout
        return _FakeResponse(201)

    with app.app_context():
        with patch.object(email_mod.urllib.request, 'urlopen', side_effect=fake_urlopen):
            ok = _send('Hello', ['to@example.com'], '<p>HTML</p>', 'Plain text')

    assert ok is True
    req = captured['request']
    assert req.full_url == email_mod.BREVO_SMTP_EMAIL_URL
    assert req.get_method() == 'POST'
    assert req.headers['Content-type'] == 'application/json'
    assert req.headers['Api-key'] == 'secret-api-key'

    body = json.loads(req.data.decode('utf-8'))
    assert body['subject'] == 'Hello'
    assert body['htmlContent'] == '<p>HTML</p>'
    assert body['textContent'] == 'Plain text'
    assert body['sender'] == {'email': 'from@example.com', 'name': 'Casita'}
    assert body['to'] == [{'email': 'to@example.com'}]
    assert captured['timeout'] == 30


def test_send_brevo_omits_text_when_not_provided(app):
    app.config['BREVO_API_KEY'] = 'k'
    app.config['MAIL_DEFAULT_SENDER'] = 'from@example.com'

    def fake_urlopen(request, timeout=30):
        return _FakeResponse(201)

    with app.app_context():
        with patch.object(email_mod.urllib.request, 'urlopen', side_effect=fake_urlopen) as m:
            _send('Subj', ['x@y.z'], '<html></html>')
            req = m.call_args[0][0]
    body = json.loads(req.data.decode('utf-8'))
    assert 'textContent' not in body


def test_send_brevo_skips_when_no_sender_email(app):
    app.config['BREVO_API_KEY'] = 'k'
    app.config['MAIL_DEFAULT_SENDER'] = ''

    with app.app_context():
        with patch.object(email_mod.urllib.request, 'urlopen') as m:
            ok = _send('S', ['a@b.com'], '<p>x</p>')
    assert ok is False
    m.assert_not_called()


def test_send_brevo_http_error_returns_false(app):
    app.config['BREVO_API_KEY'] = 'k'
    app.config['MAIL_DEFAULT_SENDER'] = 'from@example.com'

    import urllib.error

    def fake_urlopen(request, timeout=30):
        raise urllib.error.HTTPError(request.full_url, 400, 'Bad Request', hdrs=None, fp=BytesIO(b'{}'))

    with app.app_context():
        with patch.object(email_mod.urllib.request, 'urlopen', side_effect=fake_urlopen):
            ok = _send('S', ['a@b.com'], '<p>x</p>')
    assert ok is False
