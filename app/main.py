import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.v1 import tasks, metrics
from app.api import websocket

app = FastAPI(title="its-ok-gemini-v2 API", version="2.0.0")

# Wire all the communication layers together
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(websocket.router, tags=["real-time logs"])

@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}

# Serve static files (frontend) if they exist
static_files_path = os.path.join(os.path.dirname(__file__), "../static")
if os.path.exists(static_files_path):
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
