"""Deterministic opening/closing gates, measured against actual audio playout."""

import re
from dataclasses import dataclass


def spoken_farewell(text):
    words = text.casefold().replace("‘", "'").replace("’", "'")
    if "?" in words[-60:] or re.search(
        r"xayr\s+(?:dema|aytma)|hayr\s+(?:dema|aytma)", words
    ):
        return False
    return bool(
        re.search(
            r"\b(?:xayr|hayr|yaxshi qoling|salomat bo['ʻʼ]?ling|до свидания|всего доброго)[.!…\s]*$",
            words,
        )
    )


@dataclass
class OpeningGate:
    greeting_complete: bool = False
    played_at: float | None = None
    recipient_answered: bool = False
    introduction_requested: bool = False

    def introduction_due(self, now: float, drained: bool) -> bool:
        if not self.greeting_complete or not drained:
            return False
        if self.played_at is None:
            self.played_at = now
        if self.recipient_answered or self.introduction_requested:
            return False
        if now - self.played_at < 1.5:
            return False
        self.introduction_requested = True
        return True


@dataclass
class ClosingGate:
    requested_at: float | None = None
    goodbye_spoken: bool = False
    output_after_request: bool = False
    turn_complete: bool = False
    drained_at: float | None = None
    generation_active: bool = False
    last_audio_at: float | None = None

    @property
    def accepts_output(self):
        # A tool result can otherwise provoke a second goodbye or 'Tugadi'.
        # Play the already queued farewell, then close after its drain interval.
        return self.requested_at is None or not (
            self.goodbye_spoken
            and not self.generation_active
            or self.output_after_request
            and self.turn_complete
        )

    def generation_started(self):
        self.generation_active = True

    def generation_finished(self):
        self.generation_active = False

    def request(self, now: float, goodbye_spoken: bool = False):
        if self.requested_at is None:
            self.requested_at = now
        self.goodbye_spoken = self.goodbye_spoken or goodbye_spoken

    def output(self, now=None):
        if now is not None:
            self.last_audio_at = now
        if self.requested_at is not None:
            self.output_after_request = True
            self.turn_complete = False
            self.drained_at = None

    def needs_audio_finish(self, now):
        if self.requested_at is None:
            return False
        if (
            self.generation_active
            and self.last_audio_at is not None
            and (self.goodbye_spoken or self.output_after_request)
        ):
            return now - self.last_audio_at >= 0.9
        return now - self.requested_at >= 4 and not self.output_after_request

    def ready(self, now: float, drained: bool) -> bool:
        if self.requested_at is None:
            return False
        if self.generation_active and now - self.requested_at < 4:
            # Text may announce goodbye before the first/last audio packet.
            # An empty playback queue alone is not an end-of-speech signal.
            self.drained_at = None
            return False
        if not drained:
            self.drained_at = None
            return False
        # A tool-only turn is not a spoken farewell. Allow generation to finish.
        spoken = self.goodbye_spoken or (
            self.output_after_request and self.turn_complete
        )
        if not spoken and now - self.requested_at < 4:
            return False
        if self.drained_at is None:
            self.drained_at = now
        return now - self.drained_at >= 0.25
