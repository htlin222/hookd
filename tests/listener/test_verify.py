import pytest

from hookd.listener.verify import verify_signature


def test_valid_signature(webhook_secret, compute_signature_fn):
    body = b'{"action":"opened"}'
    sig = compute_signature_fn(webhook_secret, body)
    assert verify_signature(body, sig, webhook_secret) is True


def test_invalid_signature(webhook_secret):
    body = b'{"action":"opened"}'
    assert verify_signature(body, "sha256=badhex", webhook_secret) is False


def test_missing_prefix(webhook_secret):
    body = b'{"action":"opened"}'
    assert verify_signature(body, "not-a-sha256-sig", webhook_secret) is False


def test_empty_body(webhook_secret, compute_signature_fn):
    sig = compute_signature_fn(webhook_secret, b"")
    assert verify_signature(b"", sig, webhook_secret) is True
