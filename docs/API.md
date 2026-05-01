# API Documentation

## Authentication
All API endpoints require the `X-Api-Key` header.
```http
X-Api-Key: your_super_secret_api_key_here
```

## `POST /api/v1/tasks/ready`
Create a new task.

**cURL Example:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/ready \
  -H "X-Api-Key: my_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "Test App",
    "email": "user@example.com",
    "nonce": "unique-1234",
    "instruction": "Make a cool app"
  }'
```
**Response (201 Created):**
```json
{
  "id": "uuid",
  "status": "QUEUED",
  "task_name": "Test App",
  "email": "user@example.com"
}
```

## WebSocket: `ws://localhost:8000/ws/logs?task_id=<uuid>`
Streams structured logs.

**JavaScript Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/logs?task_id=abcd-1234");
ws.onmessage = (event) => {
    console.log("Log:", JSON.parse(event.data));
};
```
