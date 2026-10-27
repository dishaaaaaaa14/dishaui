"""Board-action and lesson contract (schema v1).

Coordinates are normalized to the board: (0,0) top-left, (1,1) bottom-right.
Durations are milliseconds. Speech anchors point into `LessonStep.narration`:
`{"sentence": 0, "char": 12}` means "start when the 13th character of the first
sentence is spoken".
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

SCHEMA_ID = "medha.board-action"
SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SENTENCE_RE = re.compile(r"(?<=[.!??])\s+")
ID_RE = r"^[A-Za-z][A-Za-z0-9_-]{0,31}$"
LESSON_ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"

ColorName = Literal[
    "chalk", "math", "diagram", "yellow", "red", "blue", "green", "orange", "white"
]
Region = Literal["auto", "title", "left", "center", "right", "top", "bottom", "full"]
Subject = Literal["math", "physics", "chemistry", "electronics", "ai", "general"]
ShapeName = Literal[
    "line",
    "arrow",
    "polyline",
    "circle",
    "ellipse",
    "rect",
    "axes",
    "spring",
    "block",
    "incline",
    "pulley",
    "resistor",
    "battery",
    "waveform",
    "atom",
    "graph",
    "grid",
]
Align = Literal["left", "center", "right"]\nLanguageCode = Literal["en", "hi", "kn"]
LINE_SHAPES = {"line", "arrow", "polyline"}
RECT_SHAPES = {
    "circle",
    "ellipse",
    "rect",
    "axes",
    "spring",
    "block",
    "incline",
    "pulley",
    "resistor",
    "battery",
    "waveform",
    "atom",
    "graph",
    "grid",
}


def split_sentences(text: str) -> list[str]:
    """Split narration into sentences using the same rule as the TTS stage."""
    return [part.strip() for part in SENTENCE_RE.split(text.strip()) if part.strip()]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pos(StrictModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class Rect(StrictModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _inside_board(self) -> Rect:
        if self.x + self.w > 1.001 or self.y + self.h > 1.001:
            raise ValueError("rect must fit inside the normalized board")
        return self


class TextStyle(StrictModel):
    font_size: float = Field(default=1.0, ge=0.2, le=4.0)
    color: ColorName = "chalk"
    bold: bool = False
    underline: bool = False
    align: Align = "left"


class Anchor(StrictModel):
    sentence: int = Field(default=0, ge=0)
    char: int = Field(default=0, ge=0)


class ActionBase(StrictModel):
    id: str = Field(pattern=ID_RE)
    duration_ms: int = Field(default=800, ge=50, le=120_000)
    start: Anchor | None = None


class WriteTextAction(ActionBase):
    op: Literal["write_text"]
    text: str = Field(min_length=1, max_length=2000)
    region: Region = "auto"
    rect: Rect | None = None
    style: TextStyle = Field(default_factory=TextStyle)
    speed: float = Field(default=0.045, ge=0.005, le=1.0)


class WriteMathAction(ActionBase):
    op: Literal["write_math"]
    latex: str = Field(min_length=1, max_length=1000)
    region: Region = "auto"
    rect: Rect | None = None
    font_size: float = Field(default=1.4, ge=0.3, le=4.0)
    color: ColorName = "math"
    speed: float = Field(default=0.06, ge=0.005, le=1.0)


class DrawAction(ActionBase):
    op: Literal["draw"]
    shape: ShapeName
    points: list[Pos] = Field(default_factory=list, max_length=64)
    rect: Rect | None = None
    filled: bool = False
    color: ColorName = "diagram"
    width: float = Field(default=3.0, ge=0.5, le=12.0)
    label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _geometry(self) -> DrawAction:
        if self.shape in LINE_SHAPES:
            if len(self.points) < 2:
                raise ValueError(f"{self.shape} needs at least two points")
            if self.rect is not None:
                raise ValueError(f"{self.shape} takes points, not rect")
        elif self.shape in RECT_SHAPES:
            if self.rect is None:
                raise ValueError(f"{self.shape} needs a rect")
            if self.points and len(self.points) > 1:
                raise ValueError(f"{self.shape} takes a rect, not points")
        return self


class ImageAction(ActionBase):
    op: Literal["image"]
    tags: list[str] = Field(min_length=1, max_length=8)
    rect: Rect
    fade_ms: int = Field(default=500, ge=100, le=5000)
    opacity: float = Field(default=1.0, ge=0.1, le=1.0)
    caption: str | None = Field(default=None, max_length=160)


class HighlightAction(ActionBase):
    op: Literal["highlight"]
    target: str = Field(pattern=ID_RE)
    color: ColorName = "yellow"
    width: float = Field(default=6.0, ge=1.0, le=20.0)


class EraseAction(ActionBase):
    op: Literal["erase"]
    target: str | None = Field(default=None, pattern=ID_RE)
    region: Rect | None = None

    @model_validator(mode="after")
    def _has_target(self) -> EraseAction:
        if self.target is None and self.region is None:
            raise ValueError("erase needs a target action or a region")
        return self


class PointAction(ActionBase):
    op: Literal["point"]
    at: Pos
    label: str | None = Field(default=None, max_length=120)
    color: ColorName = "yellow"


class ScrollAction(ActionBase):
    op: Literal["scroll"]
    amount: float = Field(default=0.45, gt=0.0, le=1.0)
    direction: Literal["up", "down"] = "up"


class PauseAction(ActionBase):
    op: Literal["pause"]


class ClearAction(ActionBase):
    op: Literal["clear"]


class BulletListAction(ActionBase):
    op: Literal["bullet_list"]
    items: list[str] = Field(min_length=1, max_length=12)
    region: Region = "auto"
    rect: Rect | None = None
    style: TextStyle = Field(default_factory=TextStyle)
    item_gap: float = Field(default=0.07, ge=0.02, le=0.2)
    speed: float = Field(default=0.045, ge=0.005, le=1.0)


BoardAction = Annotated[
    WriteTextAction
    | WriteMathAction
    | DrawAction
    | ImageAction
    | HighlightAction
    | EraseAction
    | PointAction
    | ScrollAction
    | PauseAction
    | ClearAction
    | BulletListAction,
    Field(discriminator="op"),
]

ACTION_MODELS: dict[str, type[ActionBase]] = {
    "write_text": WriteTextAction,
    "write_math": WriteMathAction,
    "draw": DrawAction,
    "image": ImageAction,
    "highlight": HighlightAction,
    "erase": EraseAction,
    "point": PointAction,
    "scroll": ScrollAction,
    "pause": PauseAction,
    "clear": ClearAction,
    "bullet_list": BulletListAction,
}

_ACTION_ADAPTER: TypeAdapter[BoardAction] = TypeAdapter(BoardAction)


class Checkpoint(StrictModel):
    question: str = Field(min_length=1, max_length=500)
    expected: str = Field(min_length=1, max_length=500)
    hints: list[str] = Field(default_factory=list, max_length=5)


class LessonStep(StrictModel):
    id: str = Field(pattern=ID_RE)
    concept: str = Field(min_length=1, max_length=120)
    narration: str = Field(min_length=1, max_length=4000)
    board: list[BoardAction] = Field(default_factory=list, max_length=50)
    checkpoint: Checkpoint | None = None


class LessonMeta(StrictModel):
    model: str | None = None
    prompt_version: str | None = None
    material_hash: str | None = None
    style_id: str | None = None
    created_at: str | None = None
    estimated_duration_s: float | None = Field(default=None, ge=0.0)
    sources: list[str] = Field(default_factory=list, max_length=50)


class LessonScript(StrictModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    lesson_id: str = Field(pattern=LESSON_ID_RE)
    title: str = Field(min_length=1, max_length=200)
    subject: Subject = "general"
    target_concept: str | None = Field(default=None, max_length=120)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    style_id: str = "default"
    steps: list[LessonStep] = Field(min_length=1, max_length=40)
    meta: LessonMeta = Field(default_factory=LessonMeta)

    @model_validator(mode="after")
    def _unique_ids_and_anchors(self) -> LessonScript:
        step_ids: set[str] = set()
        action_ids: set[str] = set()
        for step in self.steps:
            if step.id in step_ids:
                raise ValueError(f"duplicate step id: {step.id}")
            step_ids.add(step.id)
            sentences = split_sentences(step.narration)
            for action in step.board:
                if action.id in action_ids:
                    raise ValueError(f"duplicate action id: {action.id}")
                action_ids.add(action.id)
                if action.start is not None:
                    if action.start.sentence >= len(sentences):
                        raise ValueError(
                            f"{action.id}: sentence {action.start.sentence} out of range "
                            f"({len(sentences)} sentences)"
                        )
                    if action.start.char > len(sentences[action.start.sentence]):
                        raise ValueError(f"{action.id}: char anchor out of range")
        return self

    @model_validator(mode="after")
    def _references_exist(self) -> LessonScript:
        action_ids = {action.id for step in self.steps for action in step.board}
        for step in self.steps:
            for action in step.board:
                target = getattr(action, "target", None)
                if target is not None:
                    if target == action.id:
                        raise ValueError(f"{action.id}: target cannot be itself")
                    if target not in action_ids:
                        raise ValueError(f"{action.id}: unknown target {target}")
        return self


def action_json_schema() -> dict[str, Any]:
    return _ACTION_ADAPTER.json_schema()


def lesson_json_schema() -> dict[str, Any]:
    return LessonScript.model_json_schema()


def export_schema(directory: str | Path) -> tuple[Path, Path]:
    """Write board-action.schema.json and lesson.schema.json."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    action_path = target / "board-action.schema.json"
    lesson_path = target / "lesson.schema.json"

    action_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"{SCHEMA_ID}/v1/board-action.schema.json",
                "title": "Medha Board Action v1",
                "version": SCHEMA_VERSION,
                "schema": action_json_schema(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lesson_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"{SCHEMA_ID}/v1/lesson.schema.json",
                "title": "Medha Lesson Script v1",
                "version": SCHEMA_VERSION,
                "schema": lesson_json_schema(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return action_path, lesson_path


# --- Repair -------------------------------------------------------------
_TYPE_MAP = {
    "write_text": "write_text",
    "write_math": "write_math",
    "draw_line": "draw",
    "draw_arrow": "draw",
    "draw_circle": "draw",
    "draw_axes": "draw",
    "show_image": "image",
    "highlight": "highlight",
    "erase_region": "erase",
    "pause": "pause",
    "clear": "clear",
    "bullet_list": "bullet_list",
    "point": "point",
    "scroll": "scroll",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fix_pos(payload: Any) -> Any:
    if isinstance(payload, dict) and {"x", "y"} <= payload.keys():
        payload["x"] = _clamp(float(payload["x"]), 0.0, 1.0)
        payload["y"] = _clamp(float(payload["y"]), 0.0, 1.0)
    return payload


def _clamp_rect(rect: dict[str, Any]) -> dict[str, float]:
    x = _clamp(float(rect.get("x", 0.0)), 0.0, 1.0)
    y = _clamp(float(rect.get("y", 0.0)), 0.0, 1.0)
    w = _clamp(float(rect.get("w", 0.2)), 0.02, 1.0 - x)
    h = _clamp(float(rect.get("h", 0.08)), 0.02, 1.0 - y)
    return {"x": x, "y": y, "w": w, "h": h}


def _fix_rect(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    if isinstance(payload.get("rect"), dict):
        payload["rect"] = _clamp_rect(payload["rect"])
    region = payload.get("region")
    if isinstance(region, dict) and {"x", "y", "w", "h"} <= region.keys():
        payload["region"] = _clamp_rect(region)
    return payload


def _convert_legacy(action: dict[str, Any], index: int) -> dict[str, Any]:
    legacy_type = action.get("type")
    if "op" in action or legacy_type not in _TYPE_MAP:
        return action

    op = _TYPE_MAP[legacy_type]
    if "duration_ms" in action:
        duration_ms = action["duration_ms"]
    elif "duration" in action:
        duration_ms = int(float(action["duration"]) * 1000)
    else:
        duration_ms = 800
    converted: dict[str, Any] = {
        "op": op,
        "id": action.get("id") or f"a{index + 1}",
        "duration_ms": duration_ms,
        "start": action.get("start"),
    }
    if legacy_type == "write_text":
        converted["text"] = action.get("text") or action.get("content")
        converted["style"] = action.get("style", {})
        if isinstance(action.get("position"), dict):
            converted["rect"] = {
                "x": action["position"].get("x", 0.1),
                "y": action["position"].get("y", 0.1),
                "w": 0.4,
                "h": 0.1,
            }
    elif legacy_type == "write_math":
        converted["latex"] = action.get("latex") or action.get("text")
        if isinstance(action.get("position"), dict):
            converted["rect"] = {
                "x": action["position"].get("x", 0.1),
                "y": action["position"].get("y", 0.1),
                "w": 0.4,
                "h": 0.12,
            }
    elif legacy_type in {"draw_line", "draw_arrow"}:
        converted["shape"] = "line" if legacy_type == "draw_line" else "arrow"
        converted["points"] = [action.get("start"), action.get("end")]
        converted["color"] = action.get("color", "diagram")
    elif legacy_type == "draw_circle":
        center = action.get("center") or {"x": 0.5, "y": 0.5}
        radius = float(action.get("radius", 0.1))
        converted["shape"] = "circle"
        converted["rect"] = {
            "x": center["x"] - radius,
            "y": center["y"] - radius,
            "w": radius * 2,
            "h": radius * 2,
        }
    elif legacy_type == "draw_axes":
        origin = action.get("origin") or {"x": 0.2, "y": 0.8}
        converted["shape"] = "axes"
        converted["rect"] = {
            "x": origin["x"],
            "y": origin["y"] - float(action.get("y_length", 0.35)),
            "w": float(action.get("x_length", 0.4)),
            "h": float(action.get("y_length", 0.35)),
        }
        converted["label"] = action.get("x_label", "x")
    elif legacy_type == "show_image":
        pos = action.get("position") or {"x": 0.5, "y": 0.3}
        size = action.get("size") or {"w": 0.3, "h": 0.3}
        converted["tags"] = action.get("tags", [])
        converted["rect"] = {"x": pos["x"], "y": pos["y"], "w": size["w"], "h": size["h"]}
        converted["fade_ms"] = int(float(action.get("fade_duration", 0.5)) * 1000)
    elif legacy_type == "highlight":
        target = action.get("target") or action.get("target_step_id")
        converted["target"] = str(target) if target is not None else ""
    elif legacy_type == "erase_region":
        region = action.get("region")
        if isinstance(region, dict):
            converted["region"] = region
    elif legacy_type == "bullet_list":
        converted["items"] = action.get("items", [])
        converted["style"] = action.get("style", {})
    return converted


def repair_lesson(payload: dict[str, Any]) -> tuple[LessonScript, list[str]]:
    """Best-effort normalization before validation.

    This is deliberately conservative: it fixes coordinates, ids, durations and
    legacy `type` names, and drops anchors or targets that cannot be resolved.
    It never invents narration or geometry for high-level actions.
    """
    data = copy.deepcopy(payload)
    issues: list[str] = []
    data = {k: v for k, v in data.items() if k in LessonScript.model_fields}
    data["schema_version"] = SCHEMA_VERSION
    data.setdefault("subject", "general")
    data.setdefault("difficulty", "intermediate")
    data.setdefault("style_id", "default")

    meta = data.get("meta")
    if isinstance(meta, dict):
        data["meta"] = {k: v for k, v in meta.items() if k in LessonMeta.model_fields}

    steps = data.get("steps") or []
    if not steps:
        raise ValueError("lesson has no steps")

    seen_steps: set[str] = set()
    seen_actions: set[str] = set()
    for step_index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {step_index} is not an object")
        step = {k: v for k, v in step.items() if k in LessonStep.model_fields}
        steps[step_index] = step
        step.setdefault("id", f"s{step_index + 1}")
        if step["id"] in seen_steps:
            step["id"] = f"s{step_index + 1}"
            issues.append(f"renamed duplicate step id to {step['id']}")
        seen_steps.add(step["id"])
        step.setdefault("concept", data.get("target_concept") or data.get("title") or "concept")
        if not step.get("narration"):
            step["narration"] = "Let us look at this step."
            issues.append(f"{step['id']}: empty narration replaced")
        sentences = split_sentences(step["narration"])

        normalized: list[dict[str, Any]] = []
        for action_index, raw in enumerate(step.get("board") or []):
            if not isinstance(raw, dict):
                issues.append(f"{step['id']}: dropped non-object action")
                continue
            action = _convert_legacy(raw, action_index)
            if "duration_ms" not in action and "duration" in action:
                action["duration_ms"] = int(float(action.pop("duration")) * 1000)
            action.setdefault("duration_ms", 800)
            _fix_rect(action)
            for key in ("at", "start"):
                if key in action and isinstance(action[key], dict):
                    _fix_pos(action[key])
            if "points" in action and isinstance(action["points"], list):
                action["points"] = [_fix_pos(p) for p in action["points"] if isinstance(p, dict)]

            action_id = str(action.get("id") or f"{step['id']}_a{action_index + 1}")
            if not re.match(ID_RE, action_id) or action_id in seen_actions:
                base = re.sub(r"[^A-Za-z0-9_-]", "", action_id) or "a"
                if not base or not base[0].isalpha():
                    base = f"a{base}"
                action_id = f"{base[:24]}_{action_index + 1}"
                issues.append(f"renamed action id to {action_id}")
            action["id"] = action_id
            seen_actions.add(action_id)

            if isinstance(action.get("start"), dict):
                anchor = action["start"]
                sentence = int(anchor.get("sentence", 0))
                char = int(anchor.get("char", 0))
                if sentence >= len(sentences) or char > len(sentences[sentence]):
                    action["start"] = None
                    issues.append(f"{action_id}: dropped invalid anchor")
                else:
                    action["start"] = {"sentence": sentence, "char": char}

            op = action.get("op")
            model = ACTION_MODELS.get(str(op))
            if model is None:
                issues.append(f"{action_id}: dropped unknown op {op!r}")
                continue
            action = {k: v for k, v in action.items() if k in model.model_fields}
            normalized.append(action)

        step["board"] = normalized

    # Resolve references after all ids are known.
    all_ids = {a["id"] for s in steps for a in s.get("board", [])}
    for step in steps:
        kept: list[dict[str, Any]] = []
        for action in step.get("board", []):
            target = action.get("target")
            if isinstance(target, int):
                target = str(target)
            if target is not None:
                if target == action["id"] or target not in all_ids:
                    issues.append(f"{action['id']}: dropped dangling target {target}")
                    if action.get("op") == "highlight":
                        continue
                    action.pop("target", None)
                    if action.get("op") == "erase" and action.get("region") is None:
                        continue
                else:
                    action["target"] = target
            kept.append(action)
        step["board"] = kept

    lesson = LessonScript.model_validate(data)
    return lesson, issues


def validate_lesson(payload: dict[str, Any]) -> LessonScript:
    return LessonScript.model_validate(payload)


def validate_action(payload: dict[str, Any]) -> BoardAction:
    return _ACTION_ADAPTER.validate_python(payload)
