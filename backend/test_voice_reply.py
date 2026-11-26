import unittest

from .voice_reply import ReplyAudio, uzbek_reply


class ReplyTests(unittest.TestCase):
    def test_russian_and_untranscribed_audio_never_reach_playout(self):
        for words in ("Хорошо, когда оплатите?", "Horosho, zavtra oplachu.", ""):
            with self.subTest(words=words):
                reply = ReplyAudio()
                reply.write(b"audio", "audio/pcm;rate=24000")
                self.assertIsNone(reply.release(words))
                self.assertEqual(reply.size, 0)

    def test_russian_requests_are_answered_in_uzbek_latin(self):
        self.assertTrue(
            uzbek_reply("Ruscha aytishingiz mumkin, men tushunaman. Qaysi kun qulay?")
        )
        self.assertTrue(
            uzbek_reply("Ikki million yuz ming so‘mni ertaga berasiz. To‘g‘rimi?")
        )

    def test_audio_is_held_until_whole_reply_checked_and_released_once(self):
        reply = ReplyAudio()
        reply.write(b"first", "audio/pcm;rate=24000")
        reply.write(b"second", "audio/pcm;rate=24000")
        self.assertEqual(reply.size, 11)
        self.assertEqual(
            reply.release("Assalomu alaykum."),
            [(b"first", "audio/pcm;rate=24000"), (b"second", "audio/pcm;rate=24000")],
        )
        self.assertEqual(reply.release("Assalomu alaykum."), [])

    def test_interrupt_discards_all_pending_speech(self):
        reply = ReplyAudio()
        reply.write(b"stale", "audio/pcm;rate=24000")
        reply.reset()
        self.assertEqual(reply.release("Ha."), [])
