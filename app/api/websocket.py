import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
from app.core.redis import get_redis

router = APIRouter()

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, task_id: Optional[str] = Query(None)):
    """Real-time log streaming using Redis Pub/Sub."""
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    
    channel = f"task:logs:{task_id}" if task_id else "task:logs"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(reason=str(e))
    finally:
        await pubsub.unsubscribe(channel)
