"""Engine error types carrying a process exit code (matches bash work-kb: die
defaults to exit 1; usage errors exit 2). store.StoreError also carries .code."""
from __future__ import annotations


class CortexError(Exception):
    code = 1

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


class UsageError(CortexError):
    code = 2
