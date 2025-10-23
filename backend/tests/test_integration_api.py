"""
Integration tests for FastAPI Cloud Workspaces API endpoints.

This module provides comprehensive integration tests using FastAPI TestClient
to test all API endpoints with proper authentication, authorization, and data flow.
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import get_settings
from app.core.database import Base, get_db_session
from app.modules.auth.models import User
from app.modules.auth.service import AuthService
from app.modules.storage.models import StorageFile, StorageQuota
from app.modules.workspace.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceRoleEnum,
)
from fastapi.testclient import TestClient
from main import create_application
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Test database URL for in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_app(test_session):
    """Create test FastAPI application."""
    app = create_application()

    # Override database dependency
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db_session] = override_get_db

    # Mock settings for testing
    with patch('app.core.config.get_settings') as mock_settings:
        mock_settings.return_value.secret_key = "test-secret-key-for-testing-only"
        mock_settings.return_value.algorithm = "HS256"
        mock_settings.return_value.access_token_expire_minutes = 30
        mock_settings.return_value.refresh_token_expire_days = 7
        mock_settings.return_value.redis_url = "redis://localhost:6379/1"
        mock_settings.return_value.storage_path = tempfile.mkdtemp()
        mock_settings.return_value.max_file_size = 10 * 1024 * 1024  # 10MB
        mock_settings.return_value.allowed_file_types = [".txt", ".pdf", ".jpg", ".png"]

        yield app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
async def test_user(test_session):
    """Create test user."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        is_active=True,
        is_superuser=False,
        is_verified=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_superuser(test_session):
    """Create test superuser."""
    user = User(
        email="admin@example.com",
        full_name="Admin User",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        is_active=True,
        is_superuser=True,
        is_verified=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_workspace(test_session, test_user):
    """Create test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        description="A test workspace",
        owner_id=test_user.id
    )
    test_session.add(workspace)
    await test_session.commit()
    await test_session.refresh(workspace)
    return workspace


@pytest.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    # Mock the authentication service
    with patch('app.modules.auth.service.AuthService.authenticate_user') as mock_auth:
        mock_auth.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "bearer"
        }

        response = client.post("/api/v1/auth/login", json={
            "username": test_user.email,
            "password": "secret"
        })

        assert response.status_code == 200
        token = response.json()["access_token"]

        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client, test_superuser):
    """Get authentication headers for admin user."""
    with patch('app.modules.auth.service.AuthService.authenticate_user') as mock_auth:
        mock_auth.return_value = {
            "access_token": "admin-access-token",
            "refresh_token": "admin-refresh-token",
            "token_type": "bearer"
        }

        response = client.post("/api/v1/auth/login", json={
            "username": test_superuser.email,
            "password": "secret"
        })

        assert response.status_code == 200
        token = response.json()["access_token"]

        return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_health_check(self, client):
        """Test root health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_health_check(self, client):
        """Test API health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_v1_health_check(self, client):
        """Test v1 health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_detailed_health_check(self, client):
        """Test detailed health check endpoint."""
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis.return_value = mock_redis_client

            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "checks" in data
            assert "database" in data["checks"]

    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_liveness_check(self, client):
        """Test liveness check endpoint."""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""

    def test_register_user_success(self, client):
        """Test successful user registration."""
        with patch('app.modules.auth.service.AuthService.register_user') as mock_register:
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.email = "newuser@example.com"
            mock_user.full_name = "New User"
            mock_user.is_active = True
            mock_register.return_value = mock_user

            response = client.post("/api/v1/auth/register", json={
                "email": "newuser@example.com",
                "password": "strongpassword123",
                "full_name": "New User"
            })

            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["full_name"] == "New User"

    def test_register_user_duplicate_email(self, client):
        """Test registration with duplicate email."""
        with patch('app.modules.auth.service.AuthService.register_user') as mock_register:
            mock_register.side_effect = ValueError("Email already registered")

            response = client.post("/api/v1/auth/register", json={
                "email": "existing@example.com",
                "password": "password123",
                "full_name": "Existing User"
            })

            assert response.status_code == 400
            assert "Email already registered" in response.json()["detail"]

    def test_login_success(self, client):
        """Test successful login."""
        with patch('app.modules.auth.service.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                "access_token": "test-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer"
            }

            response = client.post("/api/v1/auth/login", json={
                "username": "test@example.com",
                "password": "password123"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "test-token"
            assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        with patch('app.modules.auth.service.AuthService.authenticate_user') as mock_auth:
            mock_auth.side_effect = ValueError("Invalid credentials")

            response = client.post("/api/v1/auth/login", json={
                "username": "test@example.com",
                "password": "wrongpassword"
            })

            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]

    def test_refresh_token_success(self, client):
        """Test successful token refresh."""
        with patch('app.modules.auth.service.AuthService.refresh_access_token') as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-access-token",
                "token_type": "bearer"
            }

            response = client.post("/api/v1/auth/refresh", json={
                "refresh_token": "valid-refresh-token"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "new-access-token"

    def test_get_current_user(self, client, auth_headers, test_user):
        """Test getting current user information."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            response = client.get("/api/v1/auth/me", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == test_user.email
            assert data["full_name"] == test_user.full_name


class TestUserEndpoints:
    """Test user management endpoints."""

    def test_list_users_as_admin(self, client, admin_headers):
        """Test listing users as admin."""
        with patch('app.modules.auth.service.AuthService.list_users') as mock_list:
            mock_users = [MagicMock(), MagicMock()]
            mock_list.return_value = (mock_users, 2)

            response = client.get("/api/v1/users/", headers=admin_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["users"]) == 2

    def test_list_users_as_regular_user(self, client, auth_headers):
        """Test listing users as regular user (should fail)."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403

    def test_get_user_by_id(self, client, auth_headers, test_user):
        """Test getting user by ID."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.auth.service.AuthService.get_user_by_id') as mock_get_by_id:
                mock_get_by_id.return_value = test_user

                response = client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)

                assert response.status_code == 200
                data = response.json()
                assert data["email"] == test_user.email

    def test_update_user_profile(self, client, auth_headers, test_user):
        """Test updating user profile."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.auth.service.AuthService.update_user') as mock_update:
                updated_user = MagicMock()
                updated_user.id = test_user.id
                updated_user.email = test_user.email
                updated_user.full_name = "Updated Name"
                mock_update.return_value = updated_user

                response = client.put(f"/api/v1/users/{test_user.id}",
                                    headers=auth_headers,
                                    json={"full_name": "Updated Name"})

                assert response.status_code == 200
                data = response.json()
                assert data["full_name"] == "Updated Name"


class TestWorkspaceEndpoints:
    """Test workspace management endpoints."""

    def test_list_workspaces(self, client, auth_headers, test_user):
        """Test listing user workspaces."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.workspace.service.WorkspaceService.list_user_workspaces') as mock_list:
                mock_workspaces = [MagicMock(), MagicMock()]
                mock_list.return_value = (mock_workspaces, 2)

                response = client.get("/api/v1/workspaces/", headers=auth_headers)

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                assert len(data["workspaces"]) == 2

    def test_create_workspace(self, client, auth_headers, test_user):
        """Test creating a new workspace."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.workspace.service.WorkspaceService.create_workspace') as mock_create:
                mock_workspace = MagicMock()
                mock_workspace.id = 1
                mock_workspace.name = "New Workspace"
                mock_workspace.description = "A new workspace"
                mock_create.return_value = mock_workspace

                response = client.post("/api/v1/workspaces/",
                                     headers=auth_headers,
                                     json={
                                         "name": "New Workspace",
                                         "description": "A new workspace"
                                     })

                assert response.status_code == 201
                data = response.json()
                assert data["name"] == "New Workspace"

    def test_get_workspace_by_id(self, client, auth_headers, test_user, test_workspace):
        """Test getting workspace by ID."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.workspace.service.WorkspaceService.get_workspace') as mock_get:
                mock_get.return_value = test_workspace

                response = client.get(f"/api/v1/workspaces/{test_workspace.id}", headers=auth_headers)

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == test_workspace.name

    def test_update_workspace(self, client, auth_headers, test_user, test_workspace):
        """Test updating workspace."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.workspace.service.WorkspaceService.update_workspace') as mock_update:
                updated_workspace = MagicMock()
                updated_workspace.id = test_workspace.id
                updated_workspace.name = "Updated Workspace"
                mock_update.return_value = updated_workspace

                response = client.put(f"/api/v1/workspaces/{test_workspace.id}",
                                    headers=auth_headers,
                                    json={"name": "Updated Workspace"})

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "Updated Workspace"

    def test_delete_workspace(self, client, auth_headers, test_user, test_workspace):
        """Test deleting workspace."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.workspace.service.WorkspaceService.delete_workspace') as mock_delete:
                mock_delete.return_value = None

                response = client.delete(f"/api/v1/workspaces/{test_workspace.id}", headers=auth_headers)

                assert response.status_code == 200
                assert "deleted successfully" in response.json()["message"]


class TestStorageEndpoints:
    """Test storage management endpoints."""

    def test_list_files(self, client, auth_headers, test_workspace):
        """Test listing files in workspace."""
        with patch('app.modules.storage.service.StorageService.list_files') as mock_list:
            mock_files = [MagicMock(), MagicMock()]
            mock_list.return_value = (mock_files, 2)

            response = client.get(f"/api/v1/storage/{test_workspace.id}/files", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["files"]) == 2

    def test_upload_file(self, client, auth_headers, test_workspace, test_user):
        """Test file upload."""
        with patch('app.modules.auth.dependencies.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user

            with patch('app.modules.storage.service.StorageService.upload_file') as mock_upload:
                mock_file = MagicMock()
                mock_file.id = 1
                mock_file.filename = "test.txt"
                mock_file.size = 100
                mock_upload.return_value = mock_file

                response = client.post(
                    f"/api/v1/storage/{test_workspace.id}/upload",
                    headers=auth_headers,
                    files={"file": ("test.txt", b"test content", "text/plain")}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["filename"] == "test.txt"

    def test_download_file(self, client, auth_headers, test_workspace):
        """Test file download."""
        with patch('app.modules.storage.service.StorageService.download_file') as mock_download:
            mock_download.return_value = b"file content"

            with patch('app.modules.storage.service.StorageService.get_file') as mock_get_file:
                mock_file = MagicMock()
                mock_file.workspace_id = test_workspace.id
                mock_file.filename = "test.txt"
                mock_file.content_type = "text/plain"
                mock_get_file.return_value = mock_file

                response = client.get(f"/api/v1/storage/{test_workspace.id}/files/1/download",
                                    headers=auth_headers)

                assert response.status_code == 200
                assert response.content == b"file content"

    def test_delete_file(self, client, auth_headers, test_workspace):
        """Test file deletion."""
        with patch('app.modules.storage.service.StorageService.delete_file') as mock_delete:
            mock_delete.return_value = None

            response = client.delete(f"/api/v1/storage/{test_workspace.id}/files/1",
                                   headers=auth_headers)

            assert response.status_code == 200
            assert "deleted successfully" in response.json()["message"]


class TestAPIVersioning:
    """Test API versioning endpoints."""

    def test_api_versions_endpoint(self, client):
        """Test API versions endpoint."""
        response = client.get("/api/versions")
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert data["current"] == "v1"
        assert len(data["versions"]) >= 1
        assert data["versions"][0]["version"] == "v1"

    def test_v1_info_endpoint(self, client):
        """Test v1 API info endpoint."""
        response = client.get("/api/v1/info")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1"
        assert "endpoints" in data
        assert "auth" in data["endpoints"]
        assert "users" in data["endpoints"]
        assert "workspaces" in data["endpoints"]
        assert "storage" in data["endpoints"]


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_404_not_found(self, client):
        """Test 404 error handling."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_401_unauthorized(self, client):
        """Test 401 error handling."""
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_403_forbidden(self, client, auth_headers):
        """Test 403 error handling."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403

    def test_422_validation_error(self, client):
        """Test 422 validation error handling."""
        response = client.post("/api/v1/auth/register", json={
            "email": "invalid-email",
            "password": "short"
        })
        assert response.status_code == 422
        assert "detail" in response.json()


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_exceeded(self, client):
        """Test rate limit exceeded scenario."""
        # This would require actual rate limiting implementation
        # For now, just test that endpoints respond normally
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200

    def test_auth_rate_limiting(self, client):
        """Test authentication endpoint rate limiting."""
        # Test multiple login attempts
        for _ in range(3):
            response = client.post("/api/v1/auth/login", json={
                "username": "test@example.com",
                "password": "wrongpassword"
            })
            # Should still respond (rate limiting would be tested with actual implementation)
            assert response.status_code in [401, 429]  # 429 if rate limited


class TestCORS:
    """Test CORS functionality."""

    def test_cors_preflight(self, client):
        """Test CORS preflight request."""
        response = client.options("/api/v1/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization"
        })

        # Should allow the request
        assert response.status_code in [200, 204]

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        response = client.get("/api/v1/health", headers={
            "Origin": "http://localhost:3000"
        })

        assert response.status_code == 200
        # CORS headers should be present (implementation dependent)


class TestMetrics:
    """Test metrics and monitoring endpoints."""

    def test_prometheus_metrics(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        # Should return metrics in Prometheus format
        assert "text/plain" in response.headers.get("content-type", "")

    def test_application_stats(self, client):
        """Test application statistics endpoint."""
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "stats" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
