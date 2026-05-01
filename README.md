# ⚡ Agent Command Center

![Banner](https://via.placeholder.com/1200x300.png?text=Agent+Command+Center)

> **Autonomous AI code generation agent — generates, deploys, and iterates on web projects via GitHub Pages.**

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-black?style=for-the-badge&logo=anthropic&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

## 📌 Architecture

See the [Architecture Diagram](docs/ARCHITECTURE.md) for more info.

## 🚀 Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/agent-command-center.git
   cd agent-command-center
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your keys (GitHub, Anthropic, etc.)
   ```

3. **Start the backend:**
   ```bash
   docker-compose up -d
   ```

4. **Start the frontend (development):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Submit a task:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/tasks/ready \
     -H "X-Api-Key: your_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{"task_name": "My App", "email": "me@example.com", "nonce": "abc12345", "instruction": "Build a react app"}'
   ```

## 📚 API Reference

| Endpoint | Method | Auth | Request Body | Response |
|----------|--------|------|--------------|----------|
| `/api/v1/tasks/ready` | `POST` | `X-Api-Key` | `{task_name, email, nonce, instruction}` | `201 Created` - Task info |
| `/api/v1/tasks` | `GET` | `X-Api-Key` | N/A | `200 OK` - List of tasks |
| `/api/v1/tasks/{id}` | `GET` | `X-Api-Key` | N/A | `200 OK` - Task details |
| `/api/v1/tasks/{id}` | `DELETE`| `X-Api-Key` | N/A | `204 No Content` |
| `/ws/logs` | `WS` | N/A | N/A (Connect) | Live WebSocket Log Stream |

For more details, see [API.md](docs/API.md).

## ⚙️ Environment Variables

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `API_KEY` | ✅ | `""` | Master API Key for Auth |
| `ANTHROPIC_API_KEY` | ✅ | `""` | Claude API key |
| `COHERE_API_KEY` | ✅ | `""` | Cohere API key for embeddings |
| `DB_USER` / `DB_PASSWORD` | ❌ | `postgres` | Postgres credentials |
| `REDIS_URL` | ❌ | `redis://...` | Redis Pub/Sub backend |
| `GITHUB_APP_ID` | ✅ | `""` | GitHub app integration ID |

## 🤝 Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to get started!

## 📄 License
This project is licensed under the MIT License.