# FastAPI Cloud Workspaces - Backend

A modern FastAPI-based backend application for cloud workspaces management.

## Features

- **FastAPI Framework**: High-performance, easy to use, fast to code
- **PostgreSQL Database**: Robust relational database with async support
- **Redis Cache**: High-performance caching layer
- **MinIO Object Storage**: S3-compatible object storage
- **Structured Logging**: JSON-structured logs with rich console output
- **Docker Support**: Full containerization with docker-compose
- **Code Quality**: Pre-commit hooks with Black, isort, flake8, and more

## Quick Start

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd fastapi-cloud-workspaces/backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

6. **Start services with Docker**
   ```bash
   docker-compose up -d
   ```

7. **Run the application**
   ```bash
   uvicorn main:app --reload
   ```

## Project Structure

```
backend/
├── app/                    # Application code
│   ├── api/               # API routes
│   ├── core/              # Core functionality
│   │   ├── config.py      # Configuration management
│   │   └── logger.py      # Logging setup
│   ├── internal/          # Internal modules
│   ├── modules/           # Feature modules
│   └── templates/         # Template files
├── scripts/               # Utility scripts
├── tests/                 # Test files
├── .env.example          # Environment variables template
├── docker-compose.yml    # Docker services
├── Dockerfile           # Docker image
├── main.py             # Application entry point
└── pyproject.toml      # Project configuration
```

## Development

### Code Quality

This project uses several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Static type checking
- **bandit**: Security linting
- **pre-commit**: Git hooks for automated checks

### Running Tests

```bash
pytest
```

### API Documentation

Once the application is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker Services

The application includes the following services:

- **FastAPI App**: Main application (port 8000)
- **PostgreSQL**: Database (port 5432)
- **Redis**: Cache (port 6379)
- **MinIO**: Object storage (port 9000, console: 9001)
- **pgAdmin**: Database management (port 5050)

## Environment Variables

See `.env.example` for all available configuration options.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

This project is licensed under the MIT License.
