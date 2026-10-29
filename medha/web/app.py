"""FastAPI application exposing Medha studio capabilities to the browser."""

from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
from medha.library import LessonLibrary
from medha.library.models import LibraryFilter
from medha.web.models import (
    FrameOut,
    GenerateRequest,
    JobStatus,
    LessonSummary,
    LibraryListOut,
    OpenRequest,
)
from medha.web.sessions import STORE, Session, run_generate, run_open


def create_app() -> FastAPI:
    config.ensure_dirs()
    app = FastAPI(title="Medha Web API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}

    @app.post("/api/lessons/generate", response_model=JobStatus)
    def generate(body: GenerateRequest, background: BackgroundTasks) -> JobStatus:
        if body.language not in config.SUPPORTED_LANGUAGES:
            raise HTTPException(400, f"unsupported language {body.language!r}")
        session = STORE.create()
        options = _studio_options(
            topic=body.topic,
            subject=body.subject,
            difficulty=body.difficulty,
            audience=body.audience,
            steps=body.steps,
            language=body.language,
            tts=body.tts,
            use_rag=body.use_rag,
            use_rerank=body.use_rerank,
            use_cache=body.use_cache,
        )
        background.add_task(run_generate, session, options)
        return _job_status(session)

    @app.post("/api/lessons/open", response_model=JobStatus)
    def open_lesson_endpoint(body: OpenRequest, background: BackgroundTasks) -> JobStatus:
        path = _resolve_open_path(body)
        session = STORE.create()
        options = _studio_options(
            topic=path.stem,
            language=body.language,
            tts=body.tts,
        )
        background.add_task(run_open, session, path, options)
        return _job_status(session)

    @app.get("/api/sessions/{session_id}", response_model=JobStatus)
    def session_status(session_id: str) -> JobStatus:
        return _job_status(_require(session_id))

    @app.get("/api/sessions/{session_id}/frame", response_model=FrameOut)
    def session_frame(session_id: str, t: int = 0) -> FrameOut:
        return _require(session_id).frame(t)

    @app.get("/api/sessions/{session_id}/checkpoint")
    def session_checkpoint(session_id: str, t: int = 0):
        session = _require(session_id)
        if session.state != "ready":
            raise HTTPException(409, f"session state is {session.state}")
        return session.checkpoint(t)

    @app.post("/api/sessions/{session_id}/reset-checkpoints")
    def session_reset(session_id: str) -> dict[str, bool]:
        _require(session_id).reset_checkpoints()
        return {"ok": True}

    @app.post("/api/sessions/{session_id}/seek")
    def session_seek(session_id: str, t: int = 0) -> dict[str, int]:
        session = _require(session_id)
        session.seek(t)
        return {"t": max(0, t)}

    @app.get("/api/lessons", response_model=LibraryListOut)
    def list_lessons(
        query: str | None = None,
        subject: str | None = None,
        language: str | None = None,
        favorite: bool | None = None,
    ) -> LibraryListOut:
        library = LessonLibrary()
        lessons = library.list_lessons(
            LibraryFilter(
                query=query or None,
                subject=subject or None,
                language=language or None,
                favorite=favorite,
            )
        )
        return LibraryListOut(
            lessons=[
                LessonSummary(
                    lesson_id=item.lesson_id,
                    path=item.path,
                    title=item.title,
                    subject=item.subject,
                    difficulty=item.difficulty,
                    language=item.language,
                    steps=item.steps,
                    actions=item.actions,
                    duration_ms=item.duration_ms,
                    score=item.score,
                    favorite=item.favorite,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in lessons
            ]
        )

    @app.post("/api/lessons/{lesson_id}/favorite")
    def set_favorite(lesson_id: str, favorite: bool = True) -> dict[str, bool]:
        LessonLibrary().set_favorite(lesson_id, favorite)
        return {"favorite": favorite}

    @app.get("/api/lessons/sample")
    def sample_lesson_path() -> dict[str, str]:
        generated = config.LESSON_CONTENT_DIR / "newton.json"
        fallback = config.SPEC_DIR / "board-action" / "v1" / "examples" / "newton.json"
        path = generated if generated.is_file() else fallback
        return {"path": str(path), "exists": str(path.is_file()).lower()}

    return app


def _require(session_id: str) -> Session:
    session = STORE.get(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    return session


def _resolve_open_path(body: OpenRequest) -> Path:
    if body.path:
        path = Path(body.path).expanduser()
    else:
        generated = config.LESSON_CONTENT_DIR / "newton.json"
        fallback = config.SPEC_DIR / "board-action" / "v1" / "examples" / "newton.json"
        path = generated if generated.is_file() else fallback
    if not path.is_file():
        raise HTTPException(404, f"lesson file not found: {path}")
    return path


def _studio_options(
    *,
    topic: str,
    subject: str = "general",
    difficulty: str = "beginner",
    audience: str = config.LESSON_DEFAULT_AUDIENCE,
    steps: int = config.LESSON_DEFAULT_STEPS,
    language: str = "en",
    tts: bool = False,
    use_rag: bool = False,
    use_rerank: bool = False,
    use_cache: bool = True,
):
    from medha.studio.service import StudioOptions

    return StudioOptions(
        topic=topic,
        subject=subject,
        difficulty=difficulty,
        audience=audience,
        steps=steps,
        language=language,  # type: ignore[arg-type]
        tts=tts,
        use_rag=use_rag,
        use_rerank=use_rerank,
        use_cache=use_cache,
    )


def _job_status(session: Session) -> JobStatus:
    result = session.result
    status = JobStatus(
        session_id=session.session_id,
        state=session.state,
        progress=list(session.progress),
        error=session.error,
    )
    if result is not None:
        lesson = result.lesson
        status.title = lesson.title
        status.subject = str(lesson.subject)
        status.language = str(lesson.language)
        status.steps = len(lesson.steps)
        status.actions = sum(len(step.board) for step in lesson.steps)
        status.duration_ms = result.playback.duration_ms
        status.score = result.report.score
        status.warnings = list(result.warnings)
        status.tts_error = result.tts_error
        status.lesson_id = lesson.lesson_id
        status.path = str(result.path) if result.path is not None else None
    return status


app = create_app()
