"""PCM integrity, spectral images, jitter and interruption boundaries."""

import unittest

import numpy as np

from .voice_audio import SpeechOutput


def render(data, sizes):
    output = SpeechOutput()
    offset = 0
    for size in sizes:
        output.write(data[offset : offset + size])
        offset += size
    output.write(data[offset:])
    output.finish()
    return b"".join(output.read_frame() for _ in range(len(output.frames)))


class AudioQualityTests(unittest.TestCase):
    def test_prebuffer_silence_does_not_mark_generated_audio_as_delivered(self):
        output = SpeechOutput()
        output.read_frame()
        self.assertFalse(output.last_read_was_audio)
        output.write(np.full(300, 1000, dtype="<i2").tobytes())
        output.read_frame()
        self.assertFalse(output.last_read_was_audio)
        output.finish()
        output.read_frame()
        self.assertTrue(output.last_read_was_audio)

    def test_rate_pitch_and_high_frequency_image_rejection(self):
        t = np.arange(24000) / 24000
        source = (np.sin(2 * np.pi * 3000 * t) * 12000).astype("<i2").tobytes()
        samples = np.frombuffer(render(source, [4800] * 10), dtype="<i2")
        self.assertEqual(len(samples), 48000)
        spectrum = abs(np.fft.rfft(samples[4800:-4800]))
        frequencies = np.fft.rfftfreq(38400, 1 / 48000)
        self.assertAlmostEqual(frequencies[np.argmax(spectrum)], 3000, delta=2)
        # Linear interpolation leaves an audible spectral image at 21 kHz.
        self.assertLess(spectrum[(frequencies > 20000)].max() / spectrum.max(), 0.001)

    def test_random_and_odd_packet_boundaries_preserve_the_same_audio(self):
        source = (
            np.random.default_rng(7)
            .integers(-5000, 5000, 2400, dtype=np.int16)
            .tobytes()
        )
        full = render(source, [])
        fragmented = render(source, [1, 37, 180, 5, 7, 301, 481, 639])
        np.testing.assert_allclose(
            np.frombuffer(full, dtype="<i2"),
            np.frombuffer(fragmented, dtype="<i2"),
            atol=1,
            rtol=0,
        )

    def test_short_turn_flushes_filter_and_bypasses_startup_threshold(self):
        output = SpeechOutput()
        output.write(np.full(300, 1000, dtype="<i2").tobytes())
        self.assertFalse(output.drained)
        self.assertEqual(output.read_frame(), bytes(960))
        output.finish()
        samples = b"".join(output.read_frame() for _ in range(len(output.frames)))
        self.assertTrue(any(samples))
        self.assertTrue(output.drained)

    def test_interrupt_discards_every_pending_sample_and_starts_cleanly(self):
        output = SpeechOutput()
        output.write(np.full(4000, 1000, dtype="<i2").tobytes())
        output.reset()
        self.assertTrue(output.drained)
        self.assertEqual(output.read_frame(), bytes(960))
        output.write(np.zeros(2400, dtype="<i2").tobytes())
        output.finish()
        self.assertTrue(
            all(output.read_frame() == bytes(960) for _ in range(len(output.frames)))
        )

    def test_audio_format_cannot_accidentally_double_pitch(self):
        with self.assertRaises(ValueError):
            SpeechOutput().write(b"\0\0", "audio/pcm;rate=48000")
        with self.assertRaises(ValueError):
            SpeechOutput().write(b"\0\0", "audio/mpeg")
        output = SpeechOutput()
        output.write(b"\x01")
        with self.assertRaises(ValueError):
            output.finish()
