"""Budget enforcement engine with per-session, hourly, daily, and project limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class BudgetLimits:
    per_session: Optional[float] = None
    per_hour: Optional[float] = None
    per_day: Optional[float] = None
    per_project: Optional[float] = None


@dataclass
class SpendWindow:
    amount: float = 0.0
    start_time: float = field(default_factory=time.time)

    def reset(self) -> None:
        self.amount = 0.0
        self.start_time = time.time()


class BudgetEnforcer:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self._lock = Lock()
        self._session = SpendWindow()
        self._hourly = SpendWindow()
        self._daily = SpendWindow()
        self._project = SpendWindow()

    def record_spend(self, amount: float) -> None:
        with self._lock:
            now = time.time()
            if now - self._hourly.start_time > 3600:
                self._hourly.reset()
            if now - self._daily.start_time > 86400:
                self._daily.reset()
            self._session.amount += amount
            self._hourly.amount += amount
            self._daily.amount += amount
            self._project.amount += amount

    def check_budget(self) -> Optional[str]:
        with self._lock:
            now = time.time()
            if now - self._hourly.start_time > 3600:
                self._hourly.reset()
            if now - self._daily.start_time > 86400:
                self._daily.reset()

            if self.limits.per_session and self._session.amount >= self.limits.per_session:
                return f"Session budget exceeded: ${self._session.amount:.4f} >= ${self.limits.per_session}"
            if self.limits.per_hour and self._hourly.amount >= self.limits.per_hour:
                return f"Hourly budget exceeded: ${self._hourly.amount:.4f} >= ${self.limits.per_hour}"
            if self.limits.per_day and self._daily.amount >= self.limits.per_day:
                return f"Daily budget exceeded: ${self._daily.amount:.4f} >= ${self.limits.per_day}"
            if self.limits.per_project and self._project.amount >= self.limits.per_project:
                return f"Project budget exceeded: ${self._project.amount:.4f} >= ${self.limits.per_project}"
            return None

    def get_spend(self) -> dict[str, float]:
        with self._lock:
            return {
                "session": self._session.amount,
                "hourly": self._hourly.amount,
                "daily": self._daily.amount,
                "project": self._project.amount,
            }

    def get_remaining(self) -> dict[str, Optional[float]]:
        spend = self.get_spend()
        return {
            "session": (self.limits.per_session - spend["session"]) if self.limits.per_session else None,
            "hourly": (self.limits.per_hour - spend["hourly"]) if self.limits.per_hour else None,
            "daily": (self.limits.per_day - spend["daily"]) if self.limits.per_day else None,
            "project": (self.limits.per_project - spend["project"]) if self.limits.per_project else None,
        }

    def reset_session(self) -> None:
        with self._lock:
            self._session.reset()

    def reset_all(self) -> None:
        with self._lock:
            self._session.reset()
            self._hourly.reset()
            self._daily.reset()
            self._project.reset()
