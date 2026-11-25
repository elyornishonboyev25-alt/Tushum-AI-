import unittest

from .voice_transcription import CustomerTranscription


class TranscriptionTests(unittest.TestCase):
    def test_missing_finished_flag_on_authoritative_input_is_final(self):
        turn = CustomerTranscription()
        self.assertEqual(
            turn.accept("Завтра 2.100.000 сумов.", None),
            (0, "Завтра 2.100.000 сумов.", True),
        )
        self.assertEqual(
            turn.accept("Да, всё правильно.", None), (1, "Да, всё правильно.", True)
        )

    def test_final_replaces_interim_correction_without_duplicating_amount(self):
        turn = CustomerTranscription()
        self.assertEqual(turn.preview("Ikki million"), (0, "Ikki million", False))
        turn.preview("Ikki yuz ming emas")
        self.assertEqual(
            turn.accept("Ikki million emas, ikki yuz ming.", None),
            (0, "Ikki million emas, ikki yuz ming.", True),
        )

    def test_legacy_deltas_preserve_number_and_negation_boundaries(self):
        turn = CustomerTranscription()
        turn.accept("2 100", False)
        self.assertEqual(turn.accept(" 000 so‘m.", True), (0, "2 100 000 so‘m.", True))
        turn.accept("Ikki mil", False)
        self.assertEqual(
            turn.accept("lionni to‘lama", False), (1, "Ikki millionni to‘lama", False)
        )
        self.assertEqual(
            turn.accept("yman.", True), (1, "Ikki millionni to‘lamayman.", True)
        )

    def test_interim_hypothesis_never_becomes_a_confirmation(self):
        turn = CustomerTranscription()
        _, words, final = turn.preview("Ha, tasdiqlayman")
        self.assertEqual(words, "Ha, tasdiqlayman")
        self.assertFalse(final)
        self.assertEqual(
            turn.accept("Yo‘q, tasdiqlamayman.", None),
            (0, "Yo‘q, tasdiqlamayman.", True),
        )
