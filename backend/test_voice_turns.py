"""Timing is independent of model/network speed and paced audio backlog."""

import unittest

from .voice_turns import ClosingGate, OpeningGate


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
        self.assertFalse(gate.ready(14, True))
        self.assertFalse(gate.ready(15, True))
        self.assertTrue(gate.ready(16, True))
