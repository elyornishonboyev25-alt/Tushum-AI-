"""Timing is independent of model/network speed and paced audio backlog."""

import unittest

from .voice_turns import ClosingGate, OpeningGate, spoken_farewell


class TurnTimingTests(unittest.TestCase):
    def test_opening_wait_starts_after_playout_not_generation(self):
        gate = OpeningGate()
        self.assertFalse(gate.introduction_due(1, True))
        gate.greeting_complete = True
        self.assertFalse(gate.introduction_due(3, False))
        self.assertFalse(gate.introduction_due(10, True))
        self.assertFalse(gate.introduction_due(11.49, True))
        self.assertTrue(gate.introduction_due(11.5, True))
        self.assertFalse(gate.introduction_due(20, True))

    def test_recipient_reply_prevents_second_introduction_cue(self):
        gate = OpeningGate(greeting_complete=True)
        gate.introduction_due(1, True)
        gate.recipient_answered = True
        self.assertFalse(gate.introduction_due(4, True))

    def test_slow_farewell_cannot_be_cut_off_after_two_seconds(self):
        gate = ClosingGate()
        gate.request(1)
        gate.turn_complete = True  # A tool-only turn does not contain a farewell.
        self.assertFalse(gate.ready(4, True))
        gate.output()
        self.assertFalse(gate.ready(5, False))
        gate.turn_complete = True
        self.assertFalse(gate.ready(7, False))
        self.assertFalse(gate.ready(9, True))
        self.assertTrue(gate.ready(10, True))

    def test_goodbye_before_tool_waits_for_audio_queue(self):
        gate = ClosingGate()
        gate.request(1, goodbye_spoken=True)
        self.assertFalse(gate.ready(4, False))
        self.assertFalse(gate.ready(6, True))
        self.assertTrue(gate.ready(7, True))

    def test_provider_stall_has_bounded_shutdown(self):
        gate = ClosingGate()
        gate.request(0)
        self.assertFalse(gate.ready(3.99, True))
        self.assertFalse(gate.ready(4, True))
        self.assertTrue(gate.ready(4.25, True))

    def test_goodbye_already_queued_blocks_a_second_generated_goodbye(self):
        gate = ClosingGate()
        self.assertTrue(gate.accepts_output)
        gate.request(1, goodbye_spoken=True)
        self.assertFalse(gate.accepts_output)
        self.assertFalse(gate.ready(2, False))
        self.assertFalse(gate.ready(3, True))
        self.assertTrue(gate.ready(4, True))

    def test_disconnect_settles_for_250ms_after_actual_audio_drain(self):
        gate = ClosingGate()
        gate.request(1, True)
        self.assertFalse(gate.ready(2, False))
        self.assertFalse(gate.ready(3, True))
        self.assertFalse(gate.ready(3.24, True))
        self.assertTrue(gate.ready(3.25, True))

    def test_missing_provider_end_signal_can_flush_a_farewell_tail(self):
        gate = ClosingGate()
        gate.generation_started()
        gate.request(1, True)
        gate.output(1.1)
        self.assertFalse(gate.needs_audio_finish(1.9))
        self.assertTrue(gate.needs_audio_finish(2.01))
        gate.generation_finished()
        gate.turn_complete = True
        self.assertFalse(gate.ready(2.1, False))
        self.assertFalse(gate.ready(2.3, True))
        self.assertTrue(gate.ready(2.6, True))

    def test_only_an_actual_spoken_goodbye_starts_automatic_closing(self):
        for text in ("Rahmat, yaxshi qoling.", "Xayr!", "Mayli, salomat bo‘ling."):
            self.assertTrue(spoken_farewell(text), text)
        for text in (
            "Hali xayr demang.",
            "Xayr dedingizmi?",
            "Xayrli kun, gaplashish qulaymi?",
            "Qachon to‘laysiz?",
        ):
            self.assertFalse(spoken_farewell(text), text)

    def test_only_one_complete_reply_is_accepted_after_finish_tool(self):
        gate = ClosingGate()
        gate.request(1)
        self.assertTrue(gate.accepts_output)
        gate.output()
        self.assertTrue(gate.accepts_output)
        gate.turn_complete = True
        self.assertFalse(gate.accepts_output)
        self.assertFalse(gate.ready(3, False))

    def test_farewell_caption_before_audio_tail_does_not_cut_off_its_words(self):
        gate = ClosingGate()
        gate.generation_started()  # Spoken caption can precede its audio chunks.
        gate.request(1, goodbye_spoken=True)
        self.assertTrue(gate.accepts_output)
        self.assertFalse(gate.ready(2, True))
        self.assertFalse(gate.ready(3, True))
        gate.output()
        self.assertTrue(gate.accepts_output)
        self.assertFalse(gate.ready(2, False))
        gate.generation_finished()
        self.assertFalse(gate.accepts_output)
        self.assertFalse(gate.ready(3, True))
        self.assertTrue(gate.ready(4, True))
