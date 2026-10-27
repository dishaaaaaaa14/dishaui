"""Structured lesson quality reports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "warning", "info"]


class EvalIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Severity
    code: str
    message: str
    step_id: str | None = None
    action_id: str | None = None


class LessonReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    lesson_id: str | None = None
    title: str | None = None
    ok: bool = False
    score: int = Field(default=0, ge=0, le=100)
    steps: int = 0
    actions: int = 0
    timeline_ms: int = 0
    reading_ms: int = 0
    errors: int = 0
    warnings: int = 0
    issues: list[EvalIssue] = Field(default_factory=list)

    @property
    def infos(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "info")

    def format_text(self) -> str:
        label = self.lesson_id or self.path or "<lesson>"
        head = (
            f"{label}: {self.score}/100, {self.steps} step(s), "
            f"{self.actions} action(s), {self.timeline_ms / 1000:.1f}s"
        )
        if not self.issues:
            return head + "\n  no issues"
        order = {"error": 0, "warning": 1, "info": 2}
        lines = [head]
        for issue in sorted(self.issues, key=lambda item: order[item.severity]):
            where = ""
            if issue.step_id:
                where += f" {issue.step_id}"
            if issue.action_id:
                where += f"/{issue.action_id}"
            lines.append(
                f"  {issue.severity.upper():7} {issue.code}{where}: {issue.message}"
            )
        return "\n".join(lines)
