"""Keep audio reception running while accounting waits for a late caption.

The provider does not guarantee caption/tool ordering. Only a failed evidence
check is retried, once, after a new committed caption. No extra speech model.
"""

import asyncio


class LiveTools:
    wait_codes = frozenset(
        {"amount_required", "amount_mismatch", "confirmation_required"}
    )

    def __init__(self, execute, respond, completed, caption_sequence, *, grace=0.65):
        self.execute = execute
        self.respond = respond
        self.completed = completed
        self.caption_sequence = caption_sequence
        self.grace = grace
        self.queue = asyncio.Queue(maxsize=8)
        self.cancelled = set()
        self.caption_changed = asyncio.Event()

    def submit(self, calls):
        if self.queue.full() or len(calls) > 8:
            raise RuntimeError("voice_tool_overflow")
        self.queue.put_nowait(calls)

    def cancel(self, ids):
        self.cancelled.update(ids)
        if len(self.cancelled) > 256:
            raise RuntimeError("voice_tool_overflow")
        self.caption_changed.set()

    def caption(self):
        self.caption_changed.set()

    async def run(self):
        while True:
            calls = await self.queue.get()
            responses = []
            for call in calls:
                # Let already queued cancellation/input events run first.
                await asyncio.sleep(0)
                if call.id in self.cancelled:
                    continue
                sequence = self.caption_sequence()
                result = self.execute(call.name, dict(call.args or {}))
                if result.get("error_code") in self.wait_codes:
                    deadline = asyncio.get_running_loop().time() + self.grace
                    while (
                        call.id not in self.cancelled
                        and self.caption_sequence() == sequence
                    ):
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            break
                        self.caption_changed.clear()
                        try:
                            await asyncio.wait_for(
                                self.caption_changed.wait(), remaining
                            )
                        except TimeoutError:
                            break
                    if (
                        call.id not in self.cancelled
                        and self.caption_sequence() != sequence
                    ):
                        result = self.execute(call.name, dict(call.args or {}))
                if call.id in self.cancelled:
                    continue
                self.completed(result)
                responses.append((call, result))
            if responses:
                await self.respond(responses)
