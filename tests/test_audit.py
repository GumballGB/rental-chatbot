# Tests for the audit module, which handles logging of events to files.

from datetime import datetime
from uuid import uuid4

from core.audit import read_events, write_event
from models.event import Event


def _run_started(run_id):
    return Event(
        run_id=run_id,
        enquiry_id="ENQ-001",
        time=datetime.now(),
        type="run_started",
        model="claude-haiku-5-5",
    )


def _guard_result(run_id):
    return Event(
        run_id=run_id,
        enquiry_id="ENQ-001",
        time=datetime.now(),
        type="guard_result",
        guard="evidence_check",
        guard_passed=False,
        guard_result_reason="Citation invalide: quote introuvable en source, caractère é.",
    )


def test_write_two_events_produces_two_lines(tmp_path):
    run_id = uuid4()
    event_one = _run_started(run_id)
    event_two = _guard_result(run_id)

    run_file = write_event(event_one, audit_dir=tmp_path)
    write_event(event_two, audit_dir=tmp_path)

    lines = run_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_write_event_appends_not_overwrites(tmp_path):
    run_id = uuid4()
    run_file = write_event(_run_started(run_id), audit_dir=tmp_path)
    first_contents = run_file.read_text(encoding="utf-8")

    write_event(_guard_result(run_id), audit_dir=tmp_path)
    second_contents = run_file.read_text(encoding="utf-8")

    assert len(first_contents.splitlines()) == 1
    assert len(second_contents.splitlines()) == 2


def test_write_event_creates_missing_folder(tmp_path):
    run_id = uuid4()
    nested_dir = tmp_path / "missing" / "audit"

    run_file = write_event(_run_started(run_id), audit_dir=nested_dir)

    assert nested_dir.exists()
    assert run_file.exists()


def test_read_events_roundtrip_with_utf8_text(tmp_path):
    run_id = uuid4()
    event_one = _run_started(run_id)
    event_two = _guard_result(run_id)

    run_file = write_event(event_one, audit_dir=tmp_path)
    write_event(event_two, audit_dir=tmp_path)

    events = read_events(run_file)

    assert [event.model_dump() for event in events] == [
        event_one.model_dump(),
        event_two.model_dump(),
    ]
