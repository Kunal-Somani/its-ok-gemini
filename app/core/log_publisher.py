import json
import asyncio
from app.core.redis import publish_log


class RedisLogPublisher:
    """
    Custom structlog processor that publishes logs to Redis pub/sub.
    """

    def __call__(self, logger, method_name, event_dict):
        try:
            # Serialize event_dict; use default=str for non-serializable objects (like UUIDs)
            message = json.dumps(event_dict, default=str)
            channels = ["task:logs"]
            if "task_id" in event_dict:
                channels.append(f"task:logs:{event_dict['task_id']}")

            try:
                loop = asyncio.get_running_loop()
                for channel in channels:
                    loop.create_task(publish_log(channel, message))
            except RuntimeError:
                pass  # No running event loop to schedule async task
        except Exception:
            pass  # Fail gracefully if Redis is unavailable or serialization fails
        return event_dict
