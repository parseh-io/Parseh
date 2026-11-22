# SPDX-License-Identifier: GPL-3.0-or-later
"""The refusal and the stop switch of the transcript review tools.

The copy/paste review (asrexternal, asrcorrection, asrworkspace), the Whisper second
pass and the LM likelihood review share them.  They lived in llmconfig and llmadapter
until a0.6.3 removed the connection to a model service; the name LLMError is kept so
that the review modules and their tests read as before.
"""
import threading


class LLMError(Exception):
    """A review step refused: `code` for the page, `say` for the person."""

    def __init__(self, code, say, status=None):
        super().__init__(say)
        self.code, self.say, self.status = code, say, status


class Cancellation:
    """Set once by Stop; checked between the steps of a running review."""

    def __init__(self):
        self.event = threading.Event()

    def cancel(self):
        self.event.set()

    def check(self):
        if self.event.is_set():
            raise LLMError("cancelled", "The review was cancelled. The Whisper result is intact.")
