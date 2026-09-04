#!/usr/bin/env python3
"""Tests for BMP metronome timing, tap tempo, sound, and every GUI control."""

from __future__ import annotations

import time
import tkinter as tk
import unittest

import BMP


def pump(root: tk.Tk, times: int = 8) -> None:
    for _ in range(times):
        root.update_idletasks()
        root.update()


class ParseAndTimingTests(unittest.TestCase):
    def test_parse_common_time_signatures(self) -> None:
        self.assertEqual(BMP.parse_time_signature("1/4"), (1, 4))
        self.assertEqual(BMP.parse_time_signature("2/4"), (2, 4))
        self.assertEqual(BMP.parse_time_signature("4/4"), (4, 4))
        self.assertEqual(BMP.parse_time_signature("6/8"), (6, 8))
        self.assertEqual(BMP.parse_time_signature(" 12/8 "), (12, 8))

    def test_parse_rejects_invalid(self) -> None:
        with self.assertRaises(ValueError):
            BMP.parse_time_signature("4")
        with self.assertRaises(ValueError):
            BMP.parse_time_signature("0/4")
        with self.assertRaises(ValueError):
            BMP.parse_time_signature("4/0")

    def test_beat_interval(self) -> None:
        self.assertAlmostEqual(BMP.beat_interval_sec(60), 1.0)
        self.assertAlmostEqual(BMP.beat_interval_sec(120), 0.5)
        self.assertAlmostEqual(BMP.beat_interval_sec(90), 60.0 / 90.0)
        with self.assertRaises(ValueError):
            BMP.beat_interval_sec(0)

    def test_subdivisions_from_sound_patterns(self) -> None:
        self.assertEqual(BMP.subdivisions_for_pattern("1 Beat 1 Sound"), 1)
        self.assertEqual(BMP.subdivisions_for_pattern("1 Beat 1 2 Sound"), 2)
        self.assertEqual(BMP.subdivisions_for_pattern("1 Beat 1 2 3 Sound"), 3)
        self.assertEqual(BMP.subdivisions_for_pattern("1 Beat 1 2 3 4 Sound"), 4)

    def test_clamp_bpm_range(self) -> None:
        self.assertEqual(BMP.clamp_bpm(29), 30)
        self.assertEqual(BMP.clamp_bpm(30), 30)
        self.assertEqual(BMP.clamp_bpm(300), 300)
        self.assertEqual(BMP.clamp_bpm(301), 300)
        self.assertEqual(BMP.clamp_bpm(87.4), 87)
        self.assertEqual(BMP.clamp_bpm(87.6), 88)

    def test_next_beat_wraps_measure(self) -> None:
        self.assertEqual(BMP.next_beat(1, 2), 2)
        self.assertEqual(BMP.next_beat(2, 2), 1)
        self.assertEqual(BMP.next_beat(4, 4), 1)
        self.assertEqual(BMP.next_beat(3, 4), 4)
        with self.assertRaises(ValueError):
            BMP.next_beat(1, 0)

    def test_accent_only_on_first_downbeat(self) -> None:
        self.assertTrue(BMP.should_accent(1, 0, True))
        self.assertFalse(BMP.should_accent(1, 1, True))
        self.assertFalse(BMP.should_accent(2, 0, True))
        self.assertFalse(BMP.should_accent(1, 0, False))


class TapTempoTests(unittest.TestCase):
    def test_needs_two_taps(self) -> None:
        self.assertIsNone(BMP.tap_tempo_from_times([1.0]))

    def test_120_bpm_from_half_second_gaps(self) -> None:
        times = [0.0, 0.5, 1.0, 1.5]
        self.assertEqual(BMP.tap_tempo_from_times(times), 120)

    def test_60_bpm_from_one_second_gaps(self) -> None:
        times = [0.0, 1.0, 2.0]
        self.assertEqual(BMP.tap_tempo_from_times(times), 60)

    def test_gap_resets_series(self) -> None:
        self.assertIsNone(BMP.tap_tempo_from_times([0.0, 3.0]))

    def test_tapper_starts_new_series_after_gap(self) -> None:
        tapper = BMP.TapTempo()
        self.assertIsNone(tapper.tap(0.0))
        self.assertEqual(tapper.tap(0.5), 120)
        self.assertIsNone(tapper.tap(4.0))
        self.assertEqual(tapper.tap(4.5), 120)

    def test_tapper_clamps_to_supported_range(self) -> None:
        tapper = BMP.TapTempo()
        tapper.tap(0.0)
        self.assertEqual(tapper.tap(0.2), 300)
        tapper.reset()
        tapper.tap(0.0)
        self.assertEqual(tapper.tap(2.0), 30)


class EngineTests(unittest.TestCase):
    def test_engine_emits_accent_on_first_beat(self) -> None:
        events = []
        engine = BMP.MetronomeEngine(lambda beat, sub, kind: events.append((beat, sub, kind)))
        engine.configure(bpm=120, beats_per_measure=2, subdivisions=1, accent_on=True)
        engine.start()
        time.sleep(0.12)
        engine.stop()
        time.sleep(0.05)
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0], (1, 0, "accent"))

    def test_engine_uses_subdivision_clicks(self) -> None:
        events = []
        engine = BMP.MetronomeEngine(lambda beat, sub, kind: events.append((beat, sub, kind)))
        engine.configure(bpm=120, beats_per_measure=2, subdivisions=2, accent_on=False)
        engine.start()
        time.sleep(0.4)
        engine.stop()
        time.sleep(0.05)
        kinds = [kind for _beat, _sub, kind in events]
        self.assertIn("beat", kinds)
        self.assertIn("sub", kinds)

    def test_restart_does_not_leave_old_thread_running(self) -> None:
        engine = BMP.MetronomeEngine(lambda *_args: None)
        engine.configure(bpm=120, beats_per_measure=2, subdivisions=1)
        engine.start()
        first = engine._thread
        self.assertIsNotNone(first)
        engine.stop()
        engine.start()
        second = engine._thread
        self.assertIsNotNone(second)
        self.assertIsNot(first, second)
        self.assertFalse(first.is_alive())
        self.assertTrue(second.is_alive())
        engine.stop()
        time.sleep(0.05)
        self.assertFalse(second.is_alive())


class ClickPlayerTests(unittest.TestCase):
    def test_many_clicks_keep_playing(self) -> None:
        player = BMP.ClickPlayer()
        try:
            for _ in range(24):
                player.play("beat")
                time.sleep(0.04)
            time.sleep(0.35)
            self.assertGreaterEqual(player.play_count, 20)
            self.assertEqual(player.fail_count, 0)
        finally:
            player.close()


class ComboCatalogTests(unittest.TestCase):
    def test_time_signatures_start_with_requested_values(self) -> None:
        self.assertEqual(BMP.TIME_SIGNATURES[0], "1/4")
        self.assertEqual(BMP.TIME_SIGNATURES[1], "2/4")
        self.assertIn("4/4", BMP.TIME_SIGNATURES)
        self.assertGreater(len(BMP.TIME_SIGNATURES), 1)

    def test_sound_patterns_match_spec(self) -> None:
        self.assertEqual(BMP.SOUND_PATTERNS[0], "1 Beat 1 Sound")
        self.assertEqual(BMP.SOUND_PATTERNS[1], "1 Beat 1 2 Sound")
        self.assertGreater(len(BMP.SOUND_PATTERNS), 1)

    def test_accent_options(self) -> None:
        self.assertEqual(BMP.ACCENT_OPTIONS, ("Accent On", "Accent Off"))
        self.assertEqual(BMP.MIN_BPM, 30)
        self.assertEqual(BMP.MAX_BPM, 300)


class GuiControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.app = BMP.MetronomeApp(self.root)
        pump(self.root)

    def tearDown(self) -> None:
        try:
            self.app._on_close()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_closed_combos_show_one_selected_value(self) -> None:
        self.assertEqual(self.app.sig_box.get(), "2/4")
        self.assertEqual(self.app.sound_box.get(), "1 Beat 1 Sound")
        self.assertEqual(self.app.accent_box.get(), "Accent On")
        self.assertFalse(hasattr(self.app, "play_box"))

    def test_time_signature_dropdown_lists_all_items_and_selects(self) -> None:
        box = self.app.sig_box
        lb = box.open_dropdown()
        pump(self.root)
        self.assertGreater(len(box.dropdown_values()), 1)
        self.assertEqual(box.dropdown_values(), list(BMP.TIME_SIGNATURES))
        self.assertEqual(box.dropdown_item_count(), len(BMP.TIME_SIGNATURES))
        lb.selection_clear(0, "end")
        lb.selection_set(box.values.index("4/4"))
        box._choose()
        pump(self.root)
        self.assertEqual(box.get(), "4/4")
        self.assertEqual(self.app.engine.beats_per_measure, 4)
        self.assertIsNone(box._popup)

    def test_sound_dropdown_lists_all_items_and_selects(self) -> None:
        box = self.app.sound_box
        box.open_dropdown()
        pump(self.root)
        values = box.dropdown_values()
        self.assertGreater(len(values), 1)
        self.assertEqual(values, list(BMP.SOUND_PATTERNS))
        box.select("1 Beat 1 2 Sound")
        pump(self.root)
        self.assertEqual(box.get(), "1 Beat 1 2 Sound")
        self.assertEqual(self.app.engine.subdivisions, 2)

    def test_accent_dropdown_lists_both_items_and_selects(self) -> None:
        box = self.app.accent_box
        box.open_dropdown()
        pump(self.root)
        self.assertEqual(box.dropdown_values(), ["Accent On", "Accent Off"])
        box.select("Accent Off")
        pump(self.root)
        self.assertEqual(box.get(), "Accent Off")
        self.assertFalse(self.app.engine.accent_on)
        box.select("Accent On")
        pump(self.root)
        self.assertTrue(self.app.engine.accent_on)

    def test_bpm_dial_selects_30_to_300(self) -> None:
        dial = self.app.bpm_dial
        self.assertEqual(int(float(dial.scale.cget("from"))), 30)
        self.assertEqual(int(float(dial.scale.cget("to"))), 300)
        dial.set_bpm(30)
        pump(self.root)
        self.assertEqual(dial.get(), 30)
        self.assertEqual(self.app.engine.bpm, 30)
        dial.set_bpm(90)
        pump(self.root)
        self.assertEqual(dial.get(), 90)
        self.assertEqual(self.app.engine.bpm, 90)
        dial.set_bpm(300)
        pump(self.root)
        self.assertEqual(dial.get(), 300)
        self.assertEqual(self.app.engine.bpm, 300)
        dial.set_bpm(400)
        pump(self.root)
        self.assertEqual(dial.get(), 300)
        dial.set_bpm(10)
        pump(self.root)
        self.assertEqual(dial.get(), 30)
        dial.scale.set(72)
        pump(self.root)
        self.assertEqual(dial.get(), 72)
        self.assertEqual(self.app.engine.bpm, 72)

    def test_circle_button_toggles_play_and_stop(self) -> None:
        self.app._toggle_play()
        pump(self.root)
        self.assertTrue(self.app.engine.playing)
        self.app._toggle_play()
        pump(self.root)
        time.sleep(0.05)
        self.assertFalse(self.app.engine.playing)

    def test_tap_sets_dial_bpm(self) -> None:
        now = time.perf_counter()
        self.app.tapper.times = [now - 0.5, now]
        bpm = self.app.tapper.tap(now + 0.5)
        self.assertEqual(bpm, 120)
        self.app.bpm_dial.set_bpm(bpm)
        pump(self.root)
        self.assertEqual(self.app.bpm_dial.get(), 120)
        self.assertEqual(self.app.engine.bpm, 120)

    def test_title_and_beat_label_present(self) -> None:
        self.assertEqual(self.app.beat_label.cget("text"), "1")
        children_text = [child.cget("text") for child in self.root.winfo_children()[0].winfo_children()]
        self.assertIn("Metronome", children_text)

    def test_repeated_play_stop_keeps_single_engine_thread(self) -> None:
        threads = []
        for _ in range(4):
            self.app._start()
            pump(self.root)
            threads.append(self.app.engine._thread)
            self.app._stop()
            pump(self.root)
            time.sleep(0.03)
        self.app._start()
        pump(self.root)
        live = [thread for thread in threads if thread is not None and thread.is_alive()]
        self.assertEqual(live, [])
        self.assertTrue(self.app.engine._thread is not None and self.app.engine._thread.is_alive())
        self.app._stop()
        time.sleep(0.05)
        pump(self.root)


if __name__ == "__main__":
    unittest.main()
