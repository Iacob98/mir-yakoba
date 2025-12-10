# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Webseit is a personal blog with Telegram integration. Users authenticate via Telegram bot, and content has 4 access levels (public, registered, premium_1, premium_2).

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL + Redis
- **Frontend**: Jinja2 templates + htmx + Tailwind CSS + Editor.js
- **Bot**: aiogram 3.x (Telegram)
- **Infrastructure**: Docker Compose

## Commands

```bash
# First time setup
cp .env.example .env  # Edit with your TELEGRAM_BOT_TOKEN
./scripts/init.sh

# Start all services (app, bot, worker, db, redis)
docker compose up -d

# Run migrations
docker compose exec app alembic upgrade head

# Create new migration
docker compose exec app alembic revision --autogenerate -m "description"

# Make user admin (after they /start the bot)
docker compose exec app python scripts/make_admin.py <telegram_id>

# View logs
docker compose logs -f app
docker compose logs -f bot
docker compose logs -f worker

# Lint/format
ruff check src/
ruff format src/

# Run tests
pytest tests/
```

## Local Ports

- App: http://localhost:8000
- PostgreSQL: localhost:5433 (user: blog, pass: blog, db: blog)
- Redis: localhost:6380

## Architecture

### Services (Docker Compose)
- `app` - FastAPI web server (uvicorn with --reload)
- `bot` - Telegram bot in polling mode
- `worker` - arq background task worker (transcription, etc.)
- `db` - PostgreSQL 16
- `redis` - Redis 7 (caching, task queue)

### Entry Points
- `src/main.py` - FastAPI app, middleware, static files, lifespan
- `scripts/run_bot_polling.py` - Telegram bot in polling mode

### Routing Structure
- `/` - Web pages (`src/web/router.py`)
- `/api/v1/` - REST API (`src/api/v1/router.py`)
- `/webhook/telegram` - Bot webhook (`src/bot/webhook.py`)

### Database Models (`src/db/models/`)
- `User` - Telegram-authenticated users with `AccessLevel` enum
- `Post` - Blog posts with `PostStatus` and `PostVisibility` enums, full-text search via `TSVECTOR`
- `Media` - Uploaded images/audio/video attached to posts
- `Comment` - Post comments
- `SiteSettings` - Key-value site configuration
- `AuthCode`, `Session` - Authentication tokens

### Services (`src/services/`)
Business logic layer. Each service takes `AsyncSession` and handles one domain:
- `AuthService` - Login codes, sessions, token validation
- `PostService` - CRUD, search, visibility filtering
- `MediaService` - File uploads, transcription
- `UserService` - User management, access levels
- `NotificationService` - Telegram notifications

### Telegram Bot (`src/bot/`)
- `bot.py` - Bot/Dispatcher setup, helper functions
- `handlers/auth.py` - /start, /login commands
- `handlers/posts.py` - Post creation flow via bot

### Templates (`templates/`)
- `base.html` - Layout with Tailwind
- `pages/` - Full pages (home, post_detail, search, login)
- `partials/` - htmx fragments
- `admin/` - Admin panel pages

## Key Patterns

### Authentication Flow
1. User requests login on web → `POST /api/v1/auth/request-code`
2. System generates `AuthCode`, sends via Telegram bot
3. User enters code → `POST /api/v1/auth/verify-code`
4. Session cookie set, user authenticated

### Access Control
Posts have `visibility` (public/registered/premium_1/premium_2). Users have `access_level`. `PostService.list_posts()` filters based on user's level.

### Database Sessions
Use `get_db` dependency in FastAPI routes. For standalone scripts, use `async_session_maker` directly or `get_db_context()`.

### htmx Integration
Partials return HTML fragments. Use `hx-get`, `hx-post`, `hx-swap` attributes. Infinite scroll via `hx-trigger="revealed"`.

### Post Content Format
Posts store content as Editor.js JSON in `content_blocks` column. Rendered to HTML via `render_blocks_to_html()` in `PostService`. Legacy markdown content uses `content` column with `render_markdown()`.

## Language

UI text is in Russian. Code comments and documentation in English.
