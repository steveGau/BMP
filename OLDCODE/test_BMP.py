#!/usr/bin/env python3
"""Tests for BMP metronome timing, tap tempo, sound, and every GUI control."""

from __future__ import annotations

import os
import struct
import sys
import time
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


class LoudnessRatioTests(unittest.TestCase):
    def test_defaults_match_requested_examples(self) -> None:
        self.assertEqual(BMP.default_loudness_ratio(1), (1,))
        self.assertEqual(BMP.default_loudness_ratio(2), (2, 1))
        self.assertEqual(BMP.default_loudness_ratio(3), (2, 1, 1))
        self.assertEqual(BMP.default_loudness_ratio(4), (2, 1, 1, 1))
        self.assertEqual(BMP.default_sound_levels(10, 1), (10,))
        self.assertEqual(BMP.default_sound_levels(10, 2), (10, 1))
        self.assertEqual(BMP.default_sound_levels(10, 3), (10, 5, 1))
        self.assertEqual(BMP.default_sound_levels(10, 4), (10, 5, 3, 1))
        self.assertEqual(BMP.expand_loudness_ratio(4, 2), (4, 1))
        self.assertEqual(BMP.expand_loudness_ratio(4, 3), (4, 2, 1))
        self.assertEqual(BMP.expand_loudness_ratio(10, 4), (10, 5, 3, 1))
        self.assertEqual(BMP.resize_sound_levels((10, 5, 3, 1), 8, 4), (8, 5, 3, 1))
        self.assertEqual(BMP.format_loudness_ratio((2, 1)), "2:1")
        self.assertEqual(BMP.format_loudness_ratio((10, 5, 3, 1)), "10:5:3:1")

    def test_parse_and_gain(self) -> None:
        self.assertEqual(BMP.parse_loudness_ratio("2:1"), (2, 1))
        self.assertEqual(BMP.parse_loudness_ratio("10:5:3:1"), (10, 5, 3, 1))
        self.assertAlmostEqual(BMP.loudness_gain((2, 1), 0), 1.0)
        self.assertAlmostEqual(BMP.loudness_gain((2, 1), 1), 0.1)
        self.assertAlmostEqual(BMP.loudness_gain((10, 5, 3, 1), 0), 1.0)
        self.assertAlmostEqual(BMP.loudness_gain((10, 5, 3, 1), 1), 0.1)
        self.assertAlmostEqual(BMP.loudness_gain((10, 5, 3, 1), 2), 0.06)
        self.assertAlmostEqual(BMP.loudness_gain((10, 5, 3, 1), 3), 0.02)
        self.assertAlmostEqual(BMP.loudness_gain((10, 2), 1), 0.04)
        half = BMP.loudness_gain((2, 1), 1)
        tenth = BMP.loudness_gain((10, 1), 1)
        self.assertAlmostEqual(half / tenth, 5.0)
        self.assertAlmostEqual(BMP.loudness_gain((3, 2, 1), 1), (2 / 3) * BMP.LATER_SOUND_GAIN)
        self.assertAlmostEqual(BMP.loudness_gain((3, 2, 1), 2), (1 / 3) * BMP.LATER_SOUND_GAIN)

    def test_fraction_labels_show_half_and_quarter(self) -> None:
        self.assertEqual(BMP.ratio_fraction_labels((2, 1)), ("1", "1/2"))
        self.assertEqual(BMP.ratio_fraction_labels((4, 1)), ("1", "1/4"))
        self.assertEqual(BMP.ratio_fraction_labels((10, 5, 3, 1)), ("1", "1/2", "3/10", "1/10"))
        self.assertEqual(BMP.format_ratio_fractions((2, 1)), "1  ·  1/2")
        self.assertEqual(BMP.format_ratio_fractions((4, 1)), "1  ·  1/4")

    def test_presets_include_n_to_one_through_ten(self) -> None:
        expected = ("2:1", "3:1", "4:1", "5:1", "6:1", "7:1", "8:1", "9:1", "10:1")
        self.assertEqual(BMP.N_TO_ONE_RATIOS, expected)
        self.assertEqual(BMP.ratio_presets_for(2), expected)
        self.assertEqual(BMP.ratio_presets_for(3), expected)
        self.assertEqual(BMP.ratio_presets_for(4), expected)
        self.assertNotIn("3:2:1", BMP.ratio_presets_for(3))
        self.assertNotIn("4:3:2:1", BMP.ratio_presets_for(4))
        self.assertNotIn("10:1:1", BMP.ratio_presets_for(3))
        self.assertEqual(BMP.parse_loudness_ratio("10:1"), (10, 1))
        self.assertAlmostEqual(BMP.loudness_gain((10, 1), 1), 0.02)
        self.assertEqual(BMP.LATER_SOUND_GAIN, 0.2)
        self.assertGreater(BMP.loudness_gain((2, 1), 1), BMP.loudness_gain((5, 1), 1))
        self.assertGreater(BMP.loudness_gain((5, 1), 1), BMP.loudness_gain((10, 1), 1))
        self.assertEqual(BMP.MAX_RATIO_PART, 10)

    def test_scale_pcm_reduces_amplitude(self) -> None:
        pcm = BMP._raw_pcm(880, 20, 0.8)
        quieter = BMP._scale_pcm(pcm, 0.5)
        self.assertEqual(len(pcm), len(quieter))
        original = abs(struct.unpack_from("<h", pcm, 20)[0])
        scaled = abs(struct.unpack_from("<h", quieter, 20)[0])
        self.assertLess(scaled, original)


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
        self.assertEqual(self.app.sig_box.get(), "1/4")
        self.assertEqual(self.app.sound_box.get(), "1 Beat 1 2 Sound")
        self.assertEqual(self.app.accent_box.get(), "Accent On")
        self.assertEqual(self.app.ratio_box.get(), "10:1")
        self.assertEqual(self.app.bpm_dial.get(), 50)
        self.assertEqual(self.app.engine.bpm, 50)
        self.assertEqual(self.app.engine.beats_per_measure, 1)
        self.assertEqual(self.app.engine.subdivisions, 2)
        self.assertEqual(self.app._ratio, (10, 1))
        self.assertTrue(self.app.ratio_box._enabled)
        self.assertTrue(self.app.sound_bars[0].winfo_ismapped())
        self.assertTrue(self.app.sound_bars[1].winfo_ismapped())
        self.assertFalse(self.app.sound_bars[2].winfo_ismapped())
        self.assertEqual(str(self.app.sound_bars[0].scale.cget("state")), "disabled")
        self.assertEqual(str(self.app.sound_bars[1].scale.cget("state")), "normal")
        self.assertEqual(self.app.root.geometry().split("+")[0], "422x912")
        self.assertEqual(self.app.root.minsize(), (400, 850))
        self.assertEqual(BMP.DEFAULT_BPM, 50)
        self.assertEqual(BMP.DEFAULT_TIME_SIGNATURE, "1/4")
        self.assertEqual(BMP.DEFAULT_SOUND_PATTERN, "1 Beat 1 2 Sound")
        self.assertEqual(BMP.DEFAULT_GEOMETRY, "422x912")

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
        self.assertEqual(self.app.ratio_box.get(), "10:1")
        self.assertEqual(self.app._ratio, (10, 1))
        self.assertTrue(self.app.sound_bars[0].winfo_ismapped())
        self.assertTrue(self.app.sound_bars[1].winfo_ismapped())
        self.assertFalse(self.app.sound_bars[2].winfo_ismapped())
        self.assertEqual(str(self.app.sound_bars[1].scale.cget("state")), "normal")
        self.assertTrue(self.app.ratio_box._enabled)

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

    def test_loudness_combo_and_dials_follow_sound_pattern(self) -> None:
        app = self.app
        expected = list(BMP.N_TO_ONE_RATIOS)
        for pattern, count in (
            ("1 Beat 1 2 Sound", 2),
            ("1 Beat 1 2 3 Sound", 3),
            ("1 Beat 1 2 3 4 Sound", 4),
        ):
            app.sound_box.select(pattern)
            pump(self.root)
            app.ratio_box.open_dropdown()
            pump(self.root)
            self.assertEqual(list(app.ratio_box.dropdown_values()), expected)
            self.assertNotIn("3:2:1", app.ratio_box.dropdown_values())
            self.assertNotIn("4:3:2:1", app.ratio_box.dropdown_values())
            app.ratio_box.close_dropdown()
            pump(self.root)
            mapped = [bar.winfo_ismapped() for bar in app.sound_bars]
            self.assertEqual(mapped, [i < count for i in range(4)])

        app.sound_box.select("1 Beat 1 2 Sound")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "10:1")
        self.assertEqual(app._ratio, (10, 1))
        self.assertEqual(app.sound_bars[0].ratio_label.cget("text"), "1:1")
        self.assertEqual(app.sound_bars[1].ratio_label.cget("text"), "10:1")
        app.ratio_box.select("4:1")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "4:1")
        self.assertEqual(app._ratio, (4, 1))

        app.sound_box.select("1 Beat 1 2 3 Sound")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "4:1")
        self.assertEqual(app._ratio, (4, 2, 1))
        app.ratio_box.select("7:1")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "7:1")
        self.assertEqual(app._ratio, (7, 2, 1))

        app.sound_box.select("1 Beat 1 2 3 4 Sound")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "7:1")
        self.assertEqual(app._ratio, (7, 4, 2, 1))
        app.ratio_box.select("10:1")
        pump(self.root)
        self.assertEqual(app.ratio_box.get(), "10:1")
        self.assertEqual(app._ratio, (10, 4, 2, 1))
        app.sound_box.select("1 Beat 1 Sound")
        pump(self.root)
        app.sound_box.select("1 Beat 1 2 3 4 Sound")
        pump(self.root)
        self.assertEqual(app._ratio, (10, 5, 3, 1))
        self.assertEqual(app.sound_bars[0].ratio_label.cget("text"), "1:1")
        self.assertEqual(app.sound_bars[1].ratio_label.cget("text"), "10:5")
        self.assertEqual(app.sound_bars[2].ratio_label.cget("text"), "10:3")
        self.assertEqual(app.sound_bars[3].ratio_label.cget("text"), "10:1")
        self.assertAlmostEqual(BMP.loudness_gain(app._ratio, 0), 1.0)
        self.assertAlmostEqual(BMP.loudness_gain(app._ratio, 1), 0.1)
        self.assertAlmostEqual(BMP.loudness_gain(app._ratio, 2), 0.06)
        self.assertAlmostEqual(BMP.loudness_gain(app._ratio, 3), 0.02)
        app.sound_bars[1].set_level(8)
        pump(self.root)
        self.assertEqual(app._ratio, (10, 8, 3, 1))
        self.assertEqual(app.sound_bars[1].ratio_label.cget("text"), "10:8")

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

    def test_bpm_slider_body_click_nudge_one_step(self) -> None:
        dial = self.app.bpm_dial
        dial.set_bpm(120)
        pump(self.root)
        scale = dial.scale
        scale.update_idletasks()
        width = max(scale.winfo_width(), 1)
        height = max(scale.winfo_height(), 1)
        y = height // 2

        left_x = right_x = None
        for x in range(0, width):
            part = scale.identify(x, y)
            if part == "trough1" and left_x is None:
                left_x = x
            if part == "trough2" and right_x is None:
                right_x = x
            if left_x is not None and right_x is not None:
                break
        self.assertIsNotNone(left_x, "expected trough left of BPM handle")
        self.assertIsNotNone(right_x, "expected trough right of BPM handle")

        event = tk.Event()
        event.x = int(left_x)
        event.y = y
        self.assertEqual(dial._on_body_click(event), "break")
        pump(self.root)
        self.assertEqual(dial.get(), 119)
        self.assertEqual(self.app.engine.bpm, 119)

        event.x = int(right_x)
        self.assertEqual(dial._on_body_click(event), "break")
        pump(self.root)
        self.assertEqual(dial.get(), 120)
        self.assertEqual(self.app.engine.bpm, 120)

        dial.set_bpm(30)
        pump(self.root)
        event.x = int(left_x)
        dial._on_body_click(event)
        pump(self.root)
        self.assertEqual(dial.get(), 30)

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
