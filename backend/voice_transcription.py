"""Separate provisional subtitles from authoritative customer utterances."""

from dataclasses import dataclass


def merge_fragment(previous: str, fragment: str) -> str:
    if not previous or len(fragment) > len(previous) and fragment.startswith(previous):
        return fragment
    # Never fuzzy-overlap 'mil' + 'lion' or '100' + '000': every character
    # matters. Only a provider's authoritative final may replace a hypothesis.
    return previous + fragment


@dataclass
class CustomerTranscription:
    index: int = 0
    text: str = ""
    preview_seen: bool = False

    def preview(self, value: str):
        self.text = value
        self.preview_seen = True
        return self.index, value, False

    def accept(self, value: str, finished: bool | None):
        # Gemini 3.8 emits an authoritative full input_transcription, often with
        # finished=None. Older providers may send deltas with an explicit False.
        if finished is None or self.preview_seen and finished:
            self.text = value
        else:
            self.text = merge_fragment(self.text, value)
        final = finished is not False
        result = self.index, self.text, final
        if final:
            self.index += 1
            self.text = ""
            self.preview_seen = False
        return result
