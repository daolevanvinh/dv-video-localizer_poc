import json
from datetime import datetime
from pathlib import Path


DEBUG_DIR = Path("outputs/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def debug_log(stage: str, **values):
    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    print()
    print("=" * 80)
    print(f"[DEBUG] {timestamp} | {stage}")

    for name, value in values.items():
        if "key" in name.lower():
            print(f"{name}: <redacted>")
        else:
            print(f"{name}: {value!r}")

    print("=" * 80)


def save_debug_json(
    request_id: str,
    stage: str,
    value,
):
    path = DEBUG_DIR / f"{request_id}-{stage}.json"

    if isinstance(value, str):
        path.write_text(
            value,
            encoding="utf-8",
        )
    else:
        path.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    return path
