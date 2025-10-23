# 🚀 FastAPI Cloud Workspaces

**FastAPI Cloud Workspaces** is a modern, scalable cloud workspace management platform built with FastAPI. It provides comprehensive user authentication, workspace management, file storage, and a robust API ecosystem designed for multi-tenant cloud environments.

---

## ✨ Features

- 🧩 **Multi-Tenant Architecture** — Isolated workspaces with role-based access control
- ☁️ **Multiple Storage Backends** — Support for local storage, AWS S3, and Google Cloud Storage
- 🔐 **Secure Authentication** — JWT-based auth with refresh tokens and bcrypt password hashing
- ⚙️ **Service-Oriented Design** — Modular services for authentication, workspace, and storage management
- 🧠 **Comprehensive API** — RESTful endpoints with auto-generated OpenAPI documentation
- 🔒 **Security First** — Rate limiting, input validation, and security scanning
- 📦 **Production Ready** — Docker containerization with multi-stage builds
- 🧪 **Extensive Testing** — Unit and integration tests with 80%+ coverage
- 📊 **Monitoring & Metrics** — Health checks, Prometheus metrics, and structured logging
- 🚀 **CI/CD Pipeline** — Automated testing, security scanning, and deployment

---

## 🏗️ Project Structure

```
fastapi-cloud-workspaces/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints (auth, users, workspaces, storage, health)
│   │   ├── core/            # Core configuration, database, security
│   │   ├── models/          # SQLAlchemy database models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Business logic services
│   ├── tests/
│   │   ├── conftest.py      # Shared test fixtures and configuration
│   │   ├── test_integration_api.py  # Integration tests
│   │   └── unit/            # Unit tests for individual components
│   ├── alembic/             # Database migrations
│   ├── requirements.txt     # Production dependencies
│   ├── requirements-dev.txt # Development dependencies
│   ├── Dockerfile           # Multi-stage Docker build
│   ├── Makefile            # Development commands
│   └── main.py             # FastAPI application entry point
├── .github/workflows/       # CI/CD pipeline configuration
├── docker-compose.yml       # Local development environment
├── .env.example            # Environment variables template
└── README.md               # Project documentation
```

---

## 🧰 Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) 0.104+ |
| **Database** | PostgreSQL 15+ with SQLAlchemy 2.0 |
| **Cache** | Redis 7+ |
| **Authentication** | JWT tokens with bcrypt hashing |
| **Storage** | Local/AWS S3/Google Cloud Storage |
| **Testing** | pytest with httpx and coverage |
| **Code Quality** | Black, isort, flake8, mypy, bandit |
| **Containerization** | Docker with multi-stage builds |
| **CI/CD** | GitHub Actions |
| **Monitoring** | Prometheus metrics, structured logging |

---

## 📋 Prerequisites

- Python 3.11 or higher
- PostgreSQL 12+
- Redis 6+
- Docker and Docker Compose (optional)
- Git

---

## ⚡ Quick Start

### Option 1: Docker (Recommended)

```bash
# 1️⃣ Clone the repository
git clone https://github.com/yourusername/fastapi-cloud-workspaces.git
cd fastapi-cloud-workspaces

# 2️⃣ Copy environment configuration
cp .env.example .env
# Edit .env with your settings

# 3️⃣ Start all services
docker-compose up -d

# 4️⃣ View logs
docker-compose logs -f backend

# 5️⃣ Access the application
# API Documentation: http://localhost:8001/docs
# Health Check: http://localhost:8001/health
```

### Option 2: Manual Setup

```bash
# 1️⃣ Clone and navigate
git clone https://github.com/yourusername/fastapi-cloud-workspaces.git
cd fastapi-cloud-workspaces/backend

# 2️⃣ Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3️⃣ Install dependencies
make install-dev
# or: pip install -r requirements.txt -r requirements-dev.txt

# 4️⃣ Setup environment
cp .env.example .env
# Edit .env with your database and Redis settings

# 5️⃣ Run database migrations
make migrate

# 6️⃣ Start development server
make run
# or: uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

---

## 📚 API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **OpenAPI JSON**: http://localhost:8001/openapi.json

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info

#### Workspaces
- `GET /api/v1/workspaces/` - List user workspaces
- `POST /api/v1/workspaces/` - Create new workspace
- `GET /api/v1/workspaces/{id}` - Get workspace details
- `PUT /api/v1/workspaces/{id}` - Update workspace
- `DELETE /api/v1/workspaces/{id}` - Delete workspace

#### File Storage
- `GET /api/v1/storage/files` - List files
- `POST /api/v1/storage/upload` - Upload file
- `GET /api/v1/storage/download/{file_id}` - Download file
- `DELETE /api/v1/storage/files/{file_id}` - Delete file

#### Health & Monitoring
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system health
- `GET /metrics` - Prometheus metrics

---

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration

# Run fast tests (exclude slow ones)
make test-fast
```

### Test Structure
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test API endpoints with mocked dependencies
- **Coverage**: Maintains 80%+ code coverage
- **Fixtures**: Comprehensive test fixtures in `conftest.py`

---

## 🔧 Development

### Code Quality Tools

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make type-check

# Security scanning
make security

# Run all quality checks
make full-check
```

### Database Management

```bash
# Create new migration
make create-migration MESSAGE="Add new feature"

# Apply migrations
make migrate

# Rollback migration
make downgrade-db
```

### Available Commands

```bash
make help  # Show all available commands
```

---

## 🚀 Deployment

### Environment Configuration

Key environment variables for production:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secret-production-key

# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Cache
REDIS_URL=redis://host:port

# Storage (choose one)
STORAGE_TYPE=local|s3|gcs
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_S3_BUCKET=your-bucket-name
```

### Docker Production Deployment

```bash
# Build production image
docker build --target production -t fastapi-workspaces:latest .

# Run production container
docker run -d \
  --name fastapi-workspaces \
  -p 8001:8001 \
  --env-file .env \
  fastapi-workspaces:latest
```

---

## 📊 Monitoring

### Health Checks
- **Basic**: `/health` - Application status
- **Detailed**: `/health/detailed` - Database and Redis connectivity
- **Kubernetes**: `/health/ready` and `/health/live` probes

### Metrics
- Prometheus metrics at `/metrics`
- Application statistics at `/stats`
- Structured JSON logging

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run quality checks: `make full-check`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Guidelines
- Follow PEP 8 and use provided code formatters
- Write comprehensive tests for new features
- Update documentation as needed
- Ensure all CI checks pass

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: Interactive docs at `/docs` when running
- **Issues**: [GitHub Issues](https://github.com/yourusername/fastapi-cloud-workspaces/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/fastapi-cloud-workspaces/discussions)

---

## 🙏 Acknowledgments

Built with ❤️ using:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL toolkit
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [pytest](https://pytest.org/) - Testing framework
