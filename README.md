# CricGeo Backend

CricGeo is a modular FastAPI backend template configured for PostgreSQL.
This project is prepared as a reusable base for cricket-related products like live scores, matches, teams, and player statistics.

## Stack

- FastAPI
- SQLAlchemy (async)
- PostgreSQL (`asyncpg`)
- Alembic migrations
- JWT auth (access + refresh)
- Docker / Docker Compose

## Current Modules

- `auth`: register, login, refresh, email verification, password reset, Google OAuth callback
- `users`: user CRUD, pagination, search
- `cricket` (scaffold):
  - `matches`
  - `teams`
  - `scores`

## Project Structure

```text
app/
  core/
    config.py
    db.py
    security.py
    mailer.py
  middlewares/
    auth_middleware.py
  helpers/
    utils.py
  modules/
    auth/
    users/
    cricket/
      matches/
      teams/
      scores/
  main.py
migrations/
  versions/
```

## Environment

Default `.env` is set for your requested PostgreSQL server:





## Run Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Docker

Run backend only (external PostgreSQL):

```bash
docker-compose up -d backend
```

Run backend with local PostgreSQL profile:

```bash
docker-compose --profile local-db up -d
```

Optional pgAdmin:

```bash
docker-compose --profile local-db --profile tools up -d
```

## Next Module Development Pattern

For every new domain module, follow the same structure:

- `model.py`
- `schema.py`
- `service.py`
- `controller.py`
- `routes.py`

Then register the router in `app/main.py`.
