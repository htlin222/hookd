import json

from hookd.listener.server import EventLog


def test_event_log_writes(tmp_path):
    log_path = tmp_path / "events.jsonl"
    event_log = EventLog(log_path)

    event_log.write(
        event="push",
        action="",
        repo="owner/repo",
        sender="testuser",
        delivery_id="abc-123",
        handlers=["handlers/push.sh"],
        results=[{"handler": "handlers/push.sh", "returncode": 0, "stdout": "", "stderr": ""}],
    )

    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["event"] == "push"
    assert entry["repo"] == "owner/repo"
    assert entry["sender"] == "testuser"
    assert entry["delivery_id"] == "abc-123"
    assert entry["handlers"] == ["handlers/push.sh"]
    assert len(entry["results"]) == 1
    assert "timestamp" in entry


def test_event_log_reads(tmp_path):
    log_path = tmp_path / "events.jsonl"
    event_log = EventLog(log_path)

    # Write multiple entries
    for i in range(5):
        event_log.write(
            event="push",
            action="",
            repo="owner/repo",
            sender=f"user{i}",
            delivery_id=f"id-{i}",
            handlers=["handlers/push.sh"],
            results=[],
        )

    # Read all
    entries = event_log.read(n=10)
    assert len(entries) == 5
    assert entries[0]["sender"] == "user0"
    assert entries[4]["sender"] == "user4"

    # Read last 2
    entries = event_log.read(n=2)
    assert len(entries) == 2
    assert entries[0]["sender"] == "user3"
    assert entries[1]["sender"] == "user4"

    # Read from non-existent file
    other_log = EventLog(tmp_path / "nope.jsonl")
    assert other_log.read() == []


def test_event_log_read_skips_malformed_lines(tmp_path):
    """EventLog.read() skips corrupted JSON lines instead of crashing."""
    log_path = tmp_path / "events.jsonl"
    log_path.write_text(
        '{"event": "push", "sender": "user1"}\n'
        'THIS IS NOT JSON\n'
        '{"event": "push", "sender": "user2"}\n'
    )
    event_log = EventLog(log_path)
    entries = event_log.read(n=10)
    assert len(entries) == 2
    assert entries[0]["sender"] == "user1"
    assert entries[1]["sender"] == "user2"
