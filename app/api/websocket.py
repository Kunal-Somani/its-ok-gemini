import asyncio
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import aiofiles

router = APIRouter()

LOG_FILE_PATH = "app.log"

async def _tail_log_file(filepath: str):
    """
    Asynchronously tail a log file line by line.
    Never blocks the event loop.
    """
    # Ensure file exists
    if not os.path.exists(filepath):
        async with aiofiles.open(filepath, 'a'):
            pass

    async with aiofiles.open(filepath, "r") as f:
        # Seek to end to act as `tail -f`
        await f.seek(0, os.SEEK_END)

        while True:
            line = await f.readline()
            if not line:
                # No new data, wait before checking again
                await asyncio.sleep(0.1)
                continue
            yield line

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Log-tailing service streaming `app.log` straight to the frontend."""
    await websocket.accept()

    try:
        # Use async generator to tail logs without blocking event loop
        async for line in _tail_log_file(LOG_FILE_PATH):
            await websocket.send_text(line)
    except WebSocketDisconnect:
        # Standard closing disconnection by frontend
        pass
    except Exception as e:
        await websocket.close(reason=str(e))
