from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.computer_vision.engine import engine
from app.api import auth, academic, sessions, reporting
from app.websocket.live import router as live_router


@asynccontextmanager
async def lifespan(app):
    engine.load()
    yield


app = FastAPI(
    title="FaceIQ Campus",
    version="1.0.0",
    description="Consent-based campus attendance. Recognition accepts images, never client-supplied verified identities. All timestamps are UTC.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > 6 * 1024 * 1024:
                return await JSONResponse(
                    {"detail": "Request exceeds 6 MiB limit"}, status_code=413
                )(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body"):
                break

        async def replay():
            if chunks:
                return chunks.pop(0)
            return await receive()

        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def integrity(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Duplicate identifier, conflicting relationship, or invalid referenced record"
        },
    )


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "recognition": engine.status()}


for router in (
    auth.router,
    academic.router,
    sessions.router,
    reporting.router,
    live_router,
):
    app.include_router(router)
