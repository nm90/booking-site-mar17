"""Tests for environment-aware logging setup."""

import importlib
import logging

import pytest
from logging.handlers import RotatingFileHandler


@pytest.fixture(autouse=True)
def isolate_root_logger():
    """Ensure logger handlers do not leak across tests."""
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    yield
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()


def _load_app_module(monkeypatch, tmp_path, flask_env):
    db_path = tmp_path / "logging_test.db"
    db_path.touch()
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("FLASK_ENV", flask_env)

    import backend.app as app_module

    return importlib.reload(app_module)


def _get_rotating_file_handler(logger):
    rotating_handlers = [
        handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1
    return rotating_handlers[0]


def test_production_file_handler_level_warning(monkeypatch, tmp_path):
    app_module = _load_app_module(monkeypatch, tmp_path, "production")
    logger = app_module.setup_logging()
    file_handler = _get_rotating_file_handler(logger)

    assert file_handler.level == logging.WARNING
    assert logger.level == logging.WARNING


def test_development_file_handler_level_debug(monkeypatch, tmp_path):
    app_module = _load_app_module(monkeypatch, tmp_path, "development")
    logger = app_module.setup_logging()
    file_handler = _get_rotating_file_handler(logger)

    assert file_handler.level == logging.DEBUG
    assert logger.level == logging.DEBUG


def test_rotating_file_handler_with_rotation_settings(monkeypatch, tmp_path):
    app_module = _load_app_module(monkeypatch, tmp_path, "production")
    logger = app_module.setup_logging()
    file_handler = _get_rotating_file_handler(logger)

    assert type(file_handler) is not logging.FileHandler
    assert file_handler.maxBytes > 0
    assert file_handler.backupCount > 0


def test_setup_logging_is_idempotent(monkeypatch, tmp_path):
    app_module = _load_app_module(monkeypatch, tmp_path, "production")
    logger = app_module.setup_logging()
    logger = app_module.setup_logging()

    rotating_handlers = [
        handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
    ]
    console_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
    ]

    assert len(rotating_handlers) == 1
    assert len(console_handlers) == 1
