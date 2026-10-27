# Medha board-action spec v1.0.0

License: Apache-2.0. Version: `1.0.0`. Status: draft for the v1 demo.

The renderer owns geometry. The model emits **semantic actions**; it never emits
stroke points. This keeps the contract small, testable and model-friendly.

## Coordinate system

- Normalized board coordinates: `(0,0)` is top-left, `(1,1)` is bottom-right.
- `rect = {x, y, w, h}` must fit inside the board.
- `duration_ms` controls when an action finishes; the renderer may stretch or
  compress stroke speed to fit.
- Speech anchors are optional: `start = {sentence, char}`. `sentence` indexes
  `LessonStep.narration` split on `(?<=[.!?])\s+`; `char` indexes into that
  sentence. Omitted anchors play sequentially after the previous action.
- Colors are palette names: `chalk`, `math`, `diagram`, `yellow`, `red`, `blue`,
  `green`, `orange`, `white`.

## Lesson envelope

```json
{
  "schema_version": "1.0.0",
  "lesson_id": "newton2-demo",
  "title": "Newton's Second Law",
  "subject": "physics",
  "target_concept": "newton_second_law",
  "difficulty": "beginner",
  "style_id": "default",
  "steps": [
    {
      "id": "s1",
      "concept": "force and acceleration",
      "narration": "Force equals mass times acceleration.",
      "board": [],
      "checkpoint": null
    }
  ],
  "meta": {}
}
```

Constraints: 1â€“40 steps; unique step ids and action ids; narration 1â€“4000 chars;
`subject` is one of `math, physics, chemistry, electronics, ai, general`.

## Actions

| `op` | Purpose | Required fields |
|---|---|---|
| `write_text` | Handwritten text | `text`; optional `region`, `rect`, `style` |
| `write_math` | LaTeX rendered to vector paths | `latex`; optional `rect`, `font_size` |
| `draw` | Primitive/symbol | `shape`; `points` for line/arrow/polyline, `rect` for closed/symbol shapes |
| `image` | Bundled image lookup | `tags`, `rect` |
| `highlight` | Highlight an earlier action | `target` |
| `erase` | Erase an action or region | `target` or `region` |
| `point` | Nib/cursor emphasis | `at` |
| `scroll` | Move the board up/down | `amount` |
| `pause` | Silent beat | `duration_ms` |
| `clear` | Clear the board | none |
| `bullet_list` | Handwritten list | `items` |

`draw.shape`: `line, arrow, polyline, circle, ellipse, rect, axes, spring, block,
incline, pulley, resistor, battery, waveform, atom, graph, grid`.

`write_text.style`: `{font_size, color, bold, underline, align}`.
`write_math` uses matplotlib mathtext, not a LaTeX installation.

## Anchors and timing

```json
{"op": "write_math", "id": "a2", "latex": "F = ma", "duration_ms": 1600,
 "start": {"sentence": 0, "char": 24}}
```

The audio clock is the master clock. The director computes the spoken time of
the anchor from synthesized sentence durations and char position, then schedules
the action with `AUDIO_LEAD_MS`. An anchor outside the narration is invalid.
`repair_lesson()` drops invalid anchors and dangling targets instead of inventing
content.

## Compatibility

- Patch: documentation only.
- Minor: new optional fields or new `op` variants that old renderers can skip
  via `ACTION_MODELS`.
- Major: renamed/removed fields or changed semantics. Publish under `v2/`.

`board-action.schema.json` and `lesson.schema.json` are generated from the
Pydantic models and are the machine-readable source of truth. Examples live in
`examples/` and are checked by `python tools/export_schema.py --check`.

## Non-goals for v1

- Raw stroke geometry, fonts, colors outside the palette, or renderer hints.
- Images generated at runtime or fetched online.
- Timing in samples/frames; all timing is milliseconds and resolved by the
  director against the audio clock.
