"""Deterministic opening/closing gates, measured against actual audio playout."""

from dataclasses import dataclass


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

    @property
    def accepts_output(self):
        # A tool result can otherwise provoke a second goodbye or 'Tugadi'.
        # Play the already queued farewell, then close after its drain interval.
        return self.requested_at is None or not (
            self.goodbye_spoken or self.output_after_request and self.turn_complete
        )

    def request(self, now: float, goodbye_spoken: bool = False):
        if self.requested_at is None:
            self.requested_at = now
            self.goodbye_spoken = goodbye_spoken

    def output(self):
        if self.requested_at is not None:
            self.output_after_request = True
            self.turn_complete = False
            self.drained_at = None

    def ready(self, now: float, drained: bool) -> bool:
        if self.requested_at is None:
            return False
        if not drained:
            self.drained_at = None
            return False
        # A tool-only turn is not a spoken farewell. Allow generation to finish.
        spoken = self.goodbye_spoken or (
            self.output_after_request and self.turn_complete
        )
        if not spoken and now - self.requested_at < 15:
            return False
        if self.drained_at is None:
            self.drained_at = now
        return now - self.drained_at >= 1.0
