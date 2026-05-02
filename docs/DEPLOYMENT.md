# Archon — Deployment Guide

## 🚂 Railway Deployment
1. Connect your GitHub repository to Railway.
2. Provision a **PostgreSQL** plugin and a **Redis** plugin.
3. Add the required Environment Variables from `.env`.
4. Deploy the `Dockerfile` service. Railway will automatically pick up the root `Dockerfile`.

## ☁️ Render Deployment
1. Connect to Render.
2. Create a new "Web Service".
3. Use the `Dockerfile` in the root for the backend API.
4. Set the Health Check path to `/health`.
5. For the frontend, create a Static Site using the `frontend/` directory, set the build command to `npm run build`, and publish `dist`.

## 🐳 VPS (Ubuntu + Docker Compose)
1. SSH into your VPS.
2. Clone the repository and configure `.env` (ensure `ENVIRONMENT=production`).
3. Run `docker compose up -d --build` for all environments.
4. Run migrations: `docker-compose exec api alembic upgrade head`.

## 🌐 Custom Domain & SSL
Using the included `docker-compose.yml`, Caddy automatically grabs SSL certificates via Let's Encrypt.
Just ensure your domain's A-record points to the VPS IP and set the `DOMAIN` variable appropriately in `.env`.
