import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from prometheus_client import Counter, Histogram
import uuid
import time
import structlog
from app.api.v1 import tasks, metrics
from app.api import websocket
from app.core.config import settings
from app.core.security import limiter
from app.db.session import get_db

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
if settings.OTLP_ENDPOINT:
    exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

app = FastAPI(
    title="Archon API",
    description="Autonomous instruction-to-deployment pipeline",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "tasks", "description": "Task lifecycle management"},
        {"name": "metrics", "description": "Prometheus metrics"},
        {"name": "health", "description": "Service health checks"},
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
http_request_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    path = request.url.path
    http_requests_total.labels(
        method=request.method, path=path, status=response.status_code
    ).inc()
    http_request_duration.labels(method=request.method, path=path).observe(duration)
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire all the communication layers together
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(websocket.router, tags=["real-time logs"])


@app.get("/health", tags=["system"])
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected", "version": "1.0.0"}
    except Exception:
        raise HTTPException(503, "Database unavailable")


# Serve static files (frontend) if they exist
static_files_path = os.path.join(os.path.dirname(__file__), "../static")
if os.path.exists(static_files_path):
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
