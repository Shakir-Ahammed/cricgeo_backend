# FastAPI SaaS Backend

Production-ready FastAPI backend project with modular domain architecture, JWT authentication, and MySQL/PostgreSQL support.

## 🚀 Features

- **Modular Architecture**: Domain-driven design with separate modules (auth, users, client)
- **Database Agnostic**: MySQL by default, easily switch to PostgreSQL or other SQL databases
- **JWT Authentication**: Access + Refresh token flow with middleware
- **Async Support**: Full async/await with SQLAlchemy 2.0
- **Type Safety**: Complete type hints throughout the codebase
- **Database Migrations**: Alembic for version-controlled schema changes
- **Consistent API Responses**: Standardized response format across all endpoints
- **Clean Architecture**: Controller → Service → Model → Schema layering

## 📁 Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          # Environment configuration
│   │   ├── db.py              # Database setup and session management
│   │   └── security.py        # JWT and password hashing utilities
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── routes.py      # Auth endpoints
│   │   │   ├── controller.py  # Request/response handling
│   │   │   ├── service.py     # Business logic
│   │   │   └── schema.py      # Pydantic schemas
│   │   └── users/
│   │       ├── routes.py      # User CRUD endpoints
│   │       ├── controller.py  # Request/response handling
│   │       ├── service.py     # Business logic
│   │       ├── schema.py      # Pydantic schemas
│   │       └── model.py       # SQLAlchemy model
│   ├── helpers/
│   │   └── utils.py           # Utility functions
│   ├── middlewares/
│   │   └── auth_middleware.py # JWT verification middleware
│   └── main.py                # Application entry point
├── migrations/
│   ├── env.py                 # Alembic environment config
│   └── versions/              # Migration files
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
├── alembic.ini               # Alembic configuration
└── README.md                 # This file
```

## 🛠️ Setup Instructions

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0+ (or PostgreSQL 13+)
- pip or conda

### 2. Clone and Setup Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# For PostgreSQL support:
pip install asyncpg

# For development tools:
pip install pytest pytest-asyncio httpx black flake8 mypy
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Update these critical values:
# - DATABASE_URL (your database connection string)
# - JWT_SECRET (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### 5. Setup Database

#### MySQL Setup:
```sql
-- Create database
CREATE DATABASE saas_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (optional)
CREATE USER 'saas_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON saas_db.* TO 'saas_user'@'localhost';
FLUSH PRIVILEGES;
```

Update `.env`:
```env
DATABASE_URL=mysql+aiomysql://saas_user:your_password@localhost:3306/saas_db
```

#### PostgreSQL Setup:
```sql
-- Create database
CREATE DATABASE saas_db;

-- Create user (optional)
CREATE USER saas_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE saas_db TO saas_user;
```

Update `.env`:
```env
DATABASE_URL=postgresql+asyncpg://saas_user:your_password@localhost:5432/saas_db
```

### 6. Run Database Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 7. Run the Application

```bash
# Development mode (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 8. Access the Application

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📚 API Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login user | No |
| POST | `/auth/refresh` | Refresh access token | No |

### Users (`/users`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/users` | List users (paginated) | Yes |
| GET | `/users/{id}` | Get user by ID | Yes |
| POST | `/users` | Create new user | Yes |
| PUT | `/users/{id}` | Update user | Yes |
| DELETE | `/users/{id}` | Delete user | Yes |

### Response Format

All endpoints return a consistent JSON structure:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": {
    // Response data
  }
}
```

## 🔐 Authentication

The API uses JWT (JSON Web Tokens) for authentication.

### Login Flow

1. Register or login to get tokens:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

2. Use access token in subsequent requests:
```bash
curl http://localhost:8000/users \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

3. Refresh token when access token expires:
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

## 🗃️ Database Migrations

### Create a new migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Create empty migration
alembic revision -m "Description of changes"
```

### Apply migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>
```

### View migration history

```bash
# Show current revision
alembic current

# Show all revisions
alembic history

# Show pending migrations
alembic history --verbose
```

## 🔄 Switching Databases

The architecture supports easy database switching. Just update the `DATABASE_URL` in `.env`:

**MySQL:**
```env
DATABASE_URL=mysql+aiomysql://user:pass@localhost:3306/dbname
```

**PostgreSQL:**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
```

**SQLite (Development):**
```env
DATABASE_URL=sqlite+aiosqlite:///./database.db
```

## 📦 Adding New Modules

To add a new module (e.g., `client`):

1. Create module structure:
```bash
mkdir -p app/modules/client
touch app/modules/client/__init__.py
touch app/modules/client/model.py
touch app/modules/client/schema.py
touch app/modules/client/service.py
touch app/modules/client/controller.py
touch app/modules/client/routes.py
```

2. Define your model in `model.py`
3. Create schemas in `schema.py`
4. Implement business logic in `service.py`
5. Handle requests in `controller.py`
6. Define routes in `routes.py`
7. Register routes in `main.py`:
```python
from app.modules.client.routes import router as client_router
app.include_router(client_router)
```

8. Import model in `migrations/env.py` for Alembic:
```python
from app.modules.client.model import Client  # noqa: F401
```

## 🧪 Testing

```bash
# Install testing dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 🚀 Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Using systemd

Create `/etc/systemd/system/fastapi-saas.service`:

```ini
[Unit]
Description=FastAPI SaaS Backend
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

[Install]
WantedBy=multi-user.target
```

## 📝 Best Practices

1. **Keep routes thin** - Only handle request/response
2. **Keep controllers thin** - Only validate and delegate to services
3. **Business logic in services** - All business rules go here
4. **No DB access in controllers** - Always use services
5. **Use type hints everywhere** - Leverage Python's type system
6. **Use Pydantic schemas** - For both input and output validation
7. **Environment-driven config** - Never hardcode credentials

## 🤝 Contributing

1. Follow the existing code structure
2. Add type hints to all functions
3. Write docstrings for public methods
4. Keep services focused on single responsibility
5. Test your changes thoroughly

## 📄 License

This project is licensed under the MIT License.

## 💡 Tips

- Use `app.core.config.settings` to access configuration
- Use `Depends(get_db)` to inject database session
- Use `Depends(get_current_user)` to get authenticated user
- Use Alembic for all database schema changes
- Keep sensitive data in `.env` file
- Use the helper functions in `app.helpers.utils`

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Test database connection
python -c "from app.core.db import engine; import asyncio; asyncio.run(engine.connect())"
```

### Migration Issues

```bash
# Reset migrations (DEV ONLY)
alembic downgrade base
alembic upgrade head
```

### Import Errors

```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## 📞 Support

For issues and questions, please open an issue in the repository.
