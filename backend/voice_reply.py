"""Hold generated audio until its complete Uzbek Latin reply passes the guard."""

import re
import unicodedata


def uzbek_reply(text):
    if not text.strip():
        return False
    # Latin Uzbek output is intentional. Cyrillic customer names are rendered
    # in Latin by the agent, never used to justify speaking a Russian sentence.
    if any(c.isalpha() and "LATIN" not in unicodedata.name(c, "") for c in text):
        return False
    words = text.casefold()
    # A script/phrase guard, not proof of language or pronunciation; the model
    # also has an explicit uz-UZ speech setting and Uzbek-only policy.
    return not re.search(
        r"\b(horosho|khorosho|spasibo|pozhaluysta|dogovorilis|zdravstvuyte|"
        r"ponyal|zavtra|izvinite|oplachu|dengi|razgovarivat)\b",
        words,
    )


class ReplyAudio:
    max_bytes = 30 * 24000 * 2

    def __init__(self):
        self.reset()

    def reset(self):
        self.chunks = []
        self.size = 0

    def write(self, data, mime_type):
        if self.size + len(data) > self.max_bytes:
            self.reset()
            raise RuntimeError("audio_backlog")
        self.chunks.append((data, mime_type))
        self.size += len(data)

    def release(self, text):
        chunks = self.chunks if uzbek_reply(text) else None
        self.reset()
        return chunks
