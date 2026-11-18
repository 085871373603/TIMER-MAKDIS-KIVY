"""Pure timer/session rules for TIMER MAXDIS. No Kivy/Android imports here."""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

LORENGS = [
    {"code": "L01", "name": "LORONG 1"},
    {"code": "L02", "name": "LORONG 2"},
    {"code": "L03", "name": "LORONG 3"},
    {"code": "L04", "name": "LORONG 4"},
    {"code": "L05", "name": "LORONG 5"},
    {"code": "L06", "name": "LORONG 6"},
]


def new_state() -> dict[str, Any]:
    return {
        "schema": 1,
        "current_index": 0,
        "qty_history": [None] * len(LORENGS),
        "completed": [False] * len(LORENGS),
        "session_start_ms": 0,
        "records": [],
        "timer_active": False,
        "alarm_active": False,
        "service_active": False,
        "current_qty": 0,
        "timer_start_ms": 0,
        "timer_end_ms": 0,
        "timer_total_seconds": 0,
        "last_result": None,
    }


def load_state(path: str | os.PathLike[str]) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict) or raw.get("schema") != 1:
            return new_state()
        state = new_state()
        state.update(raw)
        # Normalize fixed-length arrays to protect the UI from damaged data.
        raw_qty = list(state.get("qty_history", []))
        normalized_qty = []
        for value in (raw_qty + [None] * 6)[:6]:
            try:
                number = int(value) if value is not None else 0
                normalized_qty.append(number if number > 0 else None)
            except (TypeError, ValueError, OverflowError):
                normalized_qty.append(None)
        state["qty_history"] = normalized_qty
        raw_done = list(state.get("completed", []))
        state["completed"] = [value is True for value in (raw_done + [False] * 6)[:6]]
        clean_records = []
        source_records = state.get("records", [])
        if isinstance(source_records, list):
            for record in source_records:
                if not isinstance(record, dict):
                    continue
                try:
                    index = int(record["index"])
                    qty = int(record["qty"])
                    started = int(record["start"])
                    finished = int(record["finish"])
                    if 0 <= index < 6 and qty > 0 and started >= 0 and finished >= started:
                        clean_records.append({"index": index, "code": str(record.get("code", LORENGS[index]["code"])), "qty": qty, "start": started, "finish": finished})
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
        state["records"] = sorted(clean_records, key=lambda item: item["index"])
        idx = int(state.get("current_index", 0))
        state["current_index"] = min(max(idx, 0), 6)
        if state["current_index"] >= 6:
            state["timer_active"] = False
        return state
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return new_state()


def save_state(path: str | os.PathLike[str], state: dict[str, Any]) -> None:
    """Atomic write: service and UI never observe a half-written JSON document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".maxdis-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass


def duration_for_qty(qty: int | float) -> int:
    """Original formula: ceil((Qty / 12) * 60) = ceil(Qty * 5) seconds."""
    value = float(qty)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Qty harus lebih besar dari 0")
    return int(math.ceil((value / 12.0) * 60.0))


def start_timer(state: dict[str, Any], qty: int, now_ms: int) -> dict[str, Any]:
    if state.get("timer_active") or state.get("alarm_active"):
        raise ValueError("Timer lorong sebelumnya belum diselesaikan")
    index = int(state.get("current_index", 0))
    if index < 0 or index >= len(LORENGS):
        raise ValueError("Sesi sudah selesai. Mulai sesi baru.")
    if isinstance(qty, bool) or int(qty) != qty or int(qty) <= 0:
        raise ValueError("Qty harus berupa bilangan bulat lebih dari 0")
    qty = int(qty)
    total = duration_for_qty(qty)
    if index == 0 and not state.get("records"):
        state["session_start_ms"] = int(now_ms)
    state["qty_history"][index] = qty
    state["completed"][index] = False
    state["current_qty"] = qty
    state["timer_start_ms"] = int(now_ms)
    state["timer_total_seconds"] = total
    state["timer_end_ms"] = int(now_ms) + total * 1000
    state["timer_active"] = True
    state["alarm_active"] = False
    state["service_active"] = True
    return state


def finish_timer(state: dict[str, Any], now_ms: int) -> bool:
    """Complete the current timer once. Returns True only on first completion."""
    if not state.get("timer_active"):
        return False
    index = int(state.get("current_index", 0))
    start = int(state.get("timer_start_ms", 0))
    qty = int(state.get("current_qty", 0))
    finish = max(int(now_ms), start)
    state["timer_active"] = False
    state["alarm_active"] = True
    state["completed"][index] = True
    state["qty_history"][index] = qty
    # Replace an existing record for this corridor to avoid duplicates after recovery.
    state["records"] = [r for r in state.get("records", []) if int(r.get("index", -1)) != index]
    state["records"].append({
        "index": index,
        "code": LORENGS[index]["code"],
        "qty": qty,
        "start": start,
        "finish": finish,
    })
    state["records"].sort(key=lambda item: int(item["index"]))
    return True


def advance_lorong(state: dict[str, Any]) -> bool:
    """Stop alarm and move to next corridor. True means all 6 corridors are done."""
    if not state.get("alarm_active"):
        raise ValueError("Timer belum selesai")
    state["alarm_active"] = False
    state["current_index"] = int(state.get("current_index", 0)) + 1
    state["timer_active"] = False
    state["timer_start_ms"] = 0
    state["timer_end_ms"] = 0
    state["timer_total_seconds"] = 0
    state["current_qty"] = 0
    if state["current_index"] >= len(LORENGS):
        state["service_active"] = False
        state["last_result"] = calculate_result(state)
        return True
    state["service_active"] = True
    return False


def reset_session() -> dict[str, Any]:
    return new_state()


def get_shift(timestamp_ms: int) -> str:
    hour = datetime.fromtimestamp(timestamp_ms / 1000).hour
    if 2 <= hour < 6:
        return "SHIFT 3"
    if 9 <= hour < 16:
        return "SHIFT 1"
    if 21 <= hour < 24:
        return "SHIFT 2"
    return "DI LUAR SHIFT"


def calculate_result(state: dict[str, Any]) -> dict[str, Any]:
    records = sorted(state.get("records", []), key=lambda item: int(item["index"]))
    total_qty = sum(int(q or 0) for q in state.get("qty_history", []))
    work_seconds = sum(max(0, int(r["finish"]) - int(r["start"])) / 1000 for r in records)
    gap_seconds = 0.0
    for previous, current in zip(records, records[1:]):
        gap_seconds += max(0, int(current["start"]) - int(previous["finish"])) / 1000
    if records:
        first_start = int(records[0]["start"])
        last_finish = int(records[-1]["finish"])
        actual_seconds = max(0, last_finish - first_start) / 1000
        finished_at = last_finish
        shift = get_shift(first_start)
    else:
        actual_seconds = 0.0
        finished_at = 0
        shift = "-"
    # Keep the original app's standard-time formula: totalQty * 5 seconds.
    target_seconds = (total_qty / 60.0) * 5.0 * 60.0
    deviation = ((actual_seconds - target_seconds) / target_seconds * 100.0) if target_seconds > 0 else 0.0
    if target_seconds <= 0:
        status = "DATA WAKTU BELUM CUKUP"
        category = "good"
    elif deviation < -10:
        status = "DISPLAY TERLALU CEPAT"
        category = "fast"
    elif deviation <= 10:
        status = "BAGUS, DISPLAY TEPAT WAKTU"
        category = "good"
    else:
        status = "DISPLAY TERLALU LAMA"
        category = "slow"
    return {
        "total_qty": total_qty,
        "shift": shift,
        "target_seconds": target_seconds,
        "work_seconds": work_seconds,
        "gap_seconds": gap_seconds,
        "actual_seconds": actual_seconds,
        "deviation_percent": deviation,
        "status": status,
        "category": category,
        "finished_at_ms": finished_at,
    }


def format_duration(total_seconds: float) -> str:
    seconds = max(0, int(math.floor(float(total_seconds) + 0.5)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def remaining_seconds(state: dict[str, Any], now_ms: int) -> int:
    if not state.get("timer_active"):
        return 0
    return max(0, int(math.ceil((int(state["timer_end_ms"]) - int(now_ms)) / 1000.0)))
