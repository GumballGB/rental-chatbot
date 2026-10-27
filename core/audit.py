"""Helpers for writing and reading per-run JSONL audit logs."""

from pathlib import Path

from models.event import Event

# The default path of the audit logs directory
DEFAULT_AUDIT_DIR = Path(__file__).resolve().parents[1] / "audit"


def write_event(event: Event, audit_dir: str | Path = DEFAULT_AUDIT_DIR) -> Path:
    """Append one event to the run's JSONL file and return the file path."""

    audit_path = Path(audit_dir)
    audit_path.mkdir(parents=True, exist_ok=True)

    run_file = audit_path / f"{event.run_id}.jsonl"
    with run_file.open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json())
        f.write("\n")

    return run_file


def read_events(path: str | Path) -> list[Event]:
    """Read a JSONL audit file back into Event objects."""

    file_path = Path(path)
    events: list[Event] = []

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(Event.model_validate_json(line))

    return events
