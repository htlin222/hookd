import pytest

from hookd.listener.verify import verify_signature, DeliveryTracker


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


def test_tracker_accepts_new():
    t = DeliveryTracker(max_size=100)
    assert t.check_and_record("d1") is True


def test_tracker_rejects_replay():
    t = DeliveryTracker(max_size=100)
    t.check_and_record("d1")
    assert t.check_and_record("d1") is False


def test_tracker_evicts_old():
    t = DeliveryTracker(max_size=2)
    t.check_and_record("d1")
    t.check_and_record("d2")
    t.check_and_record("d3")  # evicts d1
    assert t.check_and_record("d1") is True
