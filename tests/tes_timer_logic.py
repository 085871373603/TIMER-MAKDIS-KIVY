import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from timer_logic import (
    LORENGS,
    new_state,
    load_state,
    save_state,
    duration_for_qty,
    start_timer,
    finish_timer,
    advance_lorong,
    calculate_result,
    remaining_seconds,
    format_duration,
    get_shift,
)


class TimerLogicTests(unittest.TestCase):
    def test_original_duration_formula(self):
        self.assertEqual(duration_for_qty(1), 5)
        self.assertEqual(duration_for_qty(12), 60)
        self.assertEqual(duration_for_qty(120), 600)
        self.assertEqual(duration_for_qty(1.01), 6)

    def test_invalid_qty_rejected(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                duration_for_qty(value)
        with self.assertRaises(ValueError):
            start_timer(new_state(), 0, 1000)

    def test_deadline_and_remaining(self):
        state = start_timer(new_state(), 120, 1_000_000)
        self.assertEqual(state["timer_end_ms"], 1_600_000)
        self.assertEqual(remaining_seconds(state, 1_000_000), 600)
        self.assertEqual(remaining_seconds(state, 1_599_100), 1)
        self.assertEqual(remaining_seconds(state, 1_600_001), 0)

    def test_finish_is_idempotent(self):
        state = start_timer(new_state(), 12, 10_000)
        self.assertTrue(finish_timer(state, 70_000))
        self.assertFalse(finish_timer(state, 71_000))
        self.assertEqual(len(state["records"]), 1)
        self.assertTrue(state["alarm_active"])
        self.assertTrue(state["completed"][0])

    def test_six_corridors_and_result_math(self):
        state = new_state()
        first = datetime(2026, 1, 1, 9, 0, 0).timestamp() * 1000
        cursor = int(first)
        for index in range(6):
            state = start_timer(state, 10, cursor)
            self.assertEqual(state["timer_total_seconds"], 50)
            finish_at = cursor + 50_000
            self.assertTrue(finish_timer(state, finish_at))
            all_done = advance_lorong(state)
            if index < 5:
                self.assertFalse(all_done)
                cursor = finish_at + 10_000
            else:
                self.assertTrue(all_done)
        result = state["last_result"]
        self.assertEqual(state["current_index"], 6)
        self.assertEqual(result["total_qty"], 60)
        self.assertEqual(result["work_seconds"], 300)
        self.assertEqual(result["gap_seconds"], 50)
        self.assertEqual(result["actual_seconds"], 350)
        self.assertEqual(result["target_seconds"], 300)
        self.assertAlmostEqual(result["deviation_percent"], 16.6666666667, places=5)
        self.assertEqual(result["status"], "DISPLAY TERLALU LAMA")

    def test_shift_mapping(self):
        self.assertEqual(get_shift(int(datetime(2026, 1, 1, 3).timestamp() * 1000)), "SHIFT 3")
        self.assertEqual(get_shift(int(datetime(2026, 1, 1, 10).timestamp() * 1000)), "SHIFT 1")
        self.assertEqual(get_shift(int(datetime(2026, 1, 1, 22).timestamp() * 1000)), "SHIFT 2")
        self.assertEqual(get_shift(int(datetime(2026, 1, 1, 18).timestamp() * 1000)), "DI LUAR SHIFT")

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = start_timer(new_state(), 24, 123_000)
            save_state(path, original)
            restored = load_state(path)
            self.assertEqual(restored["timer_end_ms"], 243_000)
            self.assertEqual(restored["current_qty"], 24)
            self.assertTrue(restored["timer_active"])
            # Invalid JSON must return safe initial state, never crash the app/service.
            path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(load_state(path)["current_index"], 0)

    def test_display_formatting(self):
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3661), "01:01:01")


if __name__ == "__main__":
    unittest.main()
