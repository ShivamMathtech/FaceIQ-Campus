import asyncio
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from starlette.concurrency import run_in_threadpool
from app.core.config import get_settings
from app.core.security import resolve_user
from app.db.database import SessionLocal
from app.services.common import session_scope
from app.api.sessions import summary, events

router = APIRouter()


def snapshot(token, sid):
    # Reauthorize every update: logout, expiry, deactivation and reassignment apply.
    with SessionLocal() as db:
        u = resolve_user(db, token)
        if u.role == "student":
            raise HTTPException(403, "Staff live stream only")
        session_scope(db, u, sid, True)
        return {
            "type": "snapshot",
            "summary": summary(sid, u, db),
            "events": events(sid, 0, 20, u, db)["items"],
        }


@router.websocket("/api/ws/sessions/{sid}")
async def live(ws: WebSocket, sid: str):
    if ws.headers.get("origin") not in get_settings().origins:
        await ws.close(code=4403)
        return
    await ws.accept()
    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=5)
        token = hello.get("token", "")
        if not isinstance(token, str) or len(token) > 200:
            await ws.close(code=4401)
            return
        while True:
            data = await run_in_threadpool(snapshot, token, sid)
            await ws.send_json(jsonable_encoder(data))
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=1)
                if msg.get("type") == "camera_health":
                    await ws.send_json(
                        {
                            "type": "camera_health",
                            "status": str(msg.get("status", "unknown"))[:40],
                        }
                    )
                # Bound client message processing and outbound updates to ~1 Hz.
                await asyncio.sleep(0.5)
            except asyncio.TimeoutError:
                pass
    except HTTPException as exc:
        await ws.close(code=4401 if exc.status_code == 401 else 4403)
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, RuntimeError):
        try:
            await ws.close(code=4400)
        except RuntimeError:
            pass
