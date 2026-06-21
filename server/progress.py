from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class GenerationProgress:
    active: bool = False
    percent: int = 0
    message: str = "Idle"
    log: list[str] = field(default_factory=list)

    def start(self, message: str = "Starting generation...") -> None:
        self.active = True
        self.percent = 0
        self.message = message
        self.log = [self._stamp(message)]

    def update(self, percent: int, message: str) -> None:
        self.active = True
        self.percent = max(0, min(100, int(percent)))
        self.message = message
        self._append(message)

    def finish(self, message: str = "Complete") -> None:
        self.percent = 100
        self.message = message
        self._append(message)
        self.active = False

    def fail(self, message: str) -> None:
        self.message = message
        self._append(message)
        self.active = False

    def _append(self, message: str) -> None:
        line = self._stamp(message)
        if self.log and self.log[-1] == line:
            return
        self.log.append(line)
        if len(self.log) > 40:
            self.log = self.log[-40:]

    @staticmethod
    def _stamp(message: str) -> str:
        return f"{time.strftime('%H:%M:%S')}  {message}"


progress_state = GenerationProgress()
