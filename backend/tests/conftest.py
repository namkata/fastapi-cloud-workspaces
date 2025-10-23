"""
Shared test fixtures and utilities for the test suite.

This module provides common fixtures for database sessions, user creation,
workspace setup, mock storage, and other testing utilities.
"""
import asyncio
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from app.core.models import Base
from app.modules.auth.models import User
from app.modules.storage.drivers.base import BaseStorageDriver
from app.modules.storage.models import (
    FileStatus,
    StorageFile,
    StorageProvider,
    StorageQuota,
)
from app.modules.workspace.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceRoleEnum,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Test database URL for in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_db_session():
    """Create a mock database session for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "bio": "Test bio",
        "avatar_url": "https://example.com/avatar.jpg",
        "password": "SecurePassword123!",
    }


@pytest.fixture
def sample_workspace_data():
    """Sample workspace data for testing."""
    return {
        "name": "Test Workspace",
        "description": "A test workspace",
        "is_public": False,
        "max_members": 10,
        "avatar_url": "https://example.com/workspace.jpg",
    }


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        bio="Test bio",
        hashed_password="$2b$12$test_hashed_password",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Create a test superuser in the database."""
    user = User(
        id=uuid4(),
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password="$2b$12$test_hashed_password",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_workspace(db_session: AsyncSession, test_user: User) -> Workspace:
    """Create a test workspace in the database."""
    workspace = Workspace(
        id=uuid4(),
        name="Test Workspace",
        description="A test workspace",
        owner_id=test_user.id,
        is_public=False,
        max_members=10,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def workspace_roles(db_session: AsyncSession):
    """Create workspace roles in the database."""
    roles = []
    for role_enum in WorkspaceRoleEnum:
        role = WorkspaceRole(
            id=uuid4(),
            name=role_enum,
            permissions=["read", "write"] if role_enum != WorkspaceRoleEnum.VIEWER else ["read"],
            created_at=datetime.now(UTC),
        )
        roles.append(role)
        db_session.add(role)

    await db_session.commit()
    for role in roles:
        await db_session.refresh(role)

    return {role.name: role for role in roles}


@pytest_asyncio.fixture
async def test_workspace_member(
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace,
    workspace_roles
) -> WorkspaceMember:
    """Create a test workspace member in the database."""
    admin_role = workspace_roles[WorkspaceRoleEnum.ADMIN]

    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        role_id=admin_role.id,
        is_active=True,
        joined_at=datetime.now(UTC),
    )

    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member


@pytest_asyncio.fixture
async def test_storage_file(
    db_session: AsyncSession,
    test_user: User,
    test_workspace: Workspace
) -> StorageFile:
    """Create a test storage file in the database."""
    storage_file = StorageFile(
        id=uuid4(),
        file_key="test-workspace/test-file.txt",
        original_filename="test-file.txt",
        content_type="text/plain",
        file_size=1024,
        status=FileStatus.ACTIVE,
        storage_provider=StorageProvider.MINIO,
        workspace_id=test_workspace.id,
        uploaded_by=test_user.id,
        metadata={"test": "metadata"},
        folder_path="/test",
        tags=["test"],
        is_public=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db_session.add(storage_file)
    await db_session.commit()
    await db_session.refresh(storage_file)
    return storage_file


@pytest_asyncio.fixture
async def test_storage_quota(
    db_session: AsyncSession,
    test_workspace: Workspace
) -> StorageQuota:
    """Create a test storage quota in the database."""
    quota = StorageQuota(
        id=uuid4(),
        workspace_id=test_workspace.id,
        max_storage_bytes=1024 * 1024 * 1024,  # 1GB
        used_storage_bytes=1024,  # 1KB used
        max_files=1000,
        used_files=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    db_session.add(quota)
    await db_session.commit()
    await db_session.refresh(quota)
    return quota


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return Mock()


@pytest.fixture
def mock_settings():
    """Mock application settings for testing."""
    settings = Mock()
    settings.database_url = TEST_DATABASE_URL
    settings.secret_key = "test-secret-key"
    settings.algorithm = "HS256"
    settings.access_token_expire_minutes = 30
    settings.redis_url = "redis://localhost:6379/1"
    settings.storage_path = "/tmp/test_storage"
    settings.max_file_size = 10 * 1024 * 1024  # 10MB
    settings.allowed_file_types = [".txt", ".pdf", ".jpg", ".png"]
    settings.debug = True
    settings.environment = "test"
    return settings


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path

    # Clean up
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def mock_storage_path(temp_dir) -> Path:
    """Create a mock storage path for file operations."""
    storage_path = temp_dir / "storage"
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()

    with patch('redis.asyncio.from_url', return_value=mock_client):
        yield mock_client


class MockStorageDriver(BaseStorageDriver):
    """Mock storage driver for testing."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.files: Dict[str, bytes] = {}

    async def upload_file(self, key: str, content: bytes, content_type: str = None) -> Dict[str, Any]:
        """Mock file upload."""
        self.files[key] = content
        file_path = self.storage_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        return {
            "key": key,
            "size": len(content),
            "content_type": content_type,
            "etag": f"mock-etag-{hash(content)}",
            "url": f"mock://storage/{key}"
        }

    async def download_file(self, key: str) -> bytes:
        """Mock file download."""
        if key in self.files:
            return self.files[key]

        file_path = self.storage_path / key
        if file_path.exists():
            return file_path.read_bytes()

        raise FileNotFoundError(f"File not found: {key}")

    async def delete_file(self, key: str) -> bool:
        """Mock file deletion."""
        if key in self.files:
            del self.files[key]

        file_path = self.storage_path / key
        if file_path.exists():
            file_path.unlink()
            return True

        return False

    async def file_exists(self, key: str) -> bool:
        """Check if file exists."""
        return key in self.files or (self.storage_path / key).exists()

    async def get_file_info(self, key: str) -> Dict[str, Any]:
        """Get file information."""
        if not await self.file_exists(key):
            raise FileNotFoundError(f"File not found: {key}")

        file_path = self.storage_path / key
        if file_path.exists():
            stat = file_path.stat()
            return {
                "key": key,
                "size": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime),
                "etag": f"mock-etag-{stat.st_mtime}"
            }

        content = self.files[key]
        return {
            "key": key,
            "size": len(content),
            "last_modified": datetime.utcnow(),
            "etag": f"mock-etag-{hash(content)}"
        }

    async def generate_signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a mock signed URL."""
        return f"mock://signed-url/{key}?expires={expires_in}"

    async def list_files(self, prefix: str = "", limit: int = 1000) -> list:
        """List files with optional prefix."""
        files = []

        # Check in-memory files
        for key in self.files:
            if key.startswith(prefix):
                files.append({
                    "key": key,
                    "size": len(self.files[key]),
                    "last_modified": datetime.utcnow()
                })

        # Check filesystem files
        if self.storage_path.exists():
            for file_path in self.storage_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.storage_path)
                    key = str(relative_path).replace("\\", "/")
                    if key.startswith(prefix) and key not in self.files:
                        stat = file_path.stat()
                        files.append({
                            "key": key,
                            "size": stat.st_size,
                            "last_modified": datetime.fromtimestamp(stat.st_mtime)
                        })

        return files[:limit]


@pytest.fixture
def mock_storage_driver(mock_storage_path):
    """Create a mock storage driver."""
    return MockStorageDriver(mock_storage_path)


@pytest.fixture
def sample_file_content() -> bytes:
    """Generate sample file content for testing."""
    return b"This is a test file content for testing purposes."


@pytest.fixture
def sample_image_content() -> bytes:
    """Generate sample image content for testing."""
    # Simple 1x1 PNG image
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a4944415478da6300010000050001d72db3520000000049454e44ae"
        "426082"
    )


@pytest.fixture
def mock_file_upload():
    """Create a mock file upload object."""
    class MockUploadFile:
        def __init__(self, filename: str, content: bytes, content_type: str):
            self.filename = filename
            self.content = content
            self.content_type = content_type
            self.size = len(content)

        async def read(self) -> bytes:
            return self.content

        async def seek(self, position: int):
            pass

        async def close(self):
            pass

    return MockUploadFile


@pytest.fixture
def mock_auth_service():
    """Create a mock authentication service."""
    service = AsyncMock()
    service.register_user = AsyncMock()
    service.authenticate_user = AsyncMock()
    service.get_user_by_email = AsyncMock()
    service.get_user_by_id = AsyncMock()
    service.update_user = AsyncMock()
    service.delete_user = AsyncMock()
    service.verify_token = AsyncMock()
    service.refresh_access_token = AsyncMock()
    service.reset_password = AsyncMock()
    service.change_password = AsyncMock()
    service.verify_email = AsyncMock()
    service.activate_user = AsyncMock()
    service.deactivate_user = AsyncMock()
    service.list_users = AsyncMock()
    return service


@pytest.fixture
def mock_workspace_service():
    """Create a mock workspace service."""
    service = AsyncMock()
    service.create_workspace = AsyncMock()
    service.get_workspace = AsyncMock()
    service.update_workspace = AsyncMock()
    service.delete_workspace = AsyncMock()
    service.list_user_workspaces = AsyncMock()
    service.add_member = AsyncMock()
    service.remove_member = AsyncMock()
    service.update_member_role = AsyncMock()
    service.get_workspace_members = AsyncMock()
    service.is_workspace_owner = AsyncMock()
    service.can_add_members = AsyncMock()
    return service


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    service = AsyncMock()
    service.upload_file = AsyncMock()
    service.download_file = AsyncMock()
    service.delete_file = AsyncMock()
    service.get_file = AsyncMock()
    service.list_files = AsyncMock()
    service.generate_signed_url = AsyncMock()
    service.get_storage_stats = AsyncMock()
    service.get_or_create_quota = AsyncMock()
    return service


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "auth: mark test as authentication related"
    )
    config.addinivalue_line(
        "markers", "storage: mark test as storage related"
    )
    config.addinivalue_line(
        "markers", "workspace: mark test as workspace related"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "test_auth" in item.nodeid:
            item.add_marker(pytest.mark.auth)
        elif "test_storage" in item.nodeid:
            item.add_marker(pytest.mark.storage)
        elif "test_workspace" in item.nodeid:
            item.add_marker(pytest.mark.workspace)
        elif "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        # Mark slow tests
        if "slow" in item.name.lower() or "integration" in item.nodeid:
            item.add_marker(pytest.mark.slow)


# Test data generators
def generate_test_email() -> str:
    """Generate a unique test email."""
    return f"test-{uuid4()}@example.com"


def generate_test_filename(extension: str = ".txt") -> str:
    """Generate a unique test filename."""
    return f"test-file-{uuid4()}{extension}"


def generate_test_content(size: int = 100) -> bytes:
    """Generate test content of specified size."""
    return b"x" * size


class MockRequest:
    """Mock FastAPI request for testing."""

    def __init__(self, workspace_id: str = None):
        self.path_params = {"workspace_id": workspace_id} if workspace_id else {}
        self.state = Mock()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    return MockRequest()


@pytest.fixture
def mock_request_with_workspace():
    """Create a mock FastAPI request with workspace context."""
    return MockRequest(workspace_id=str(uuid4()))


# Utility functions for tests
def create_mock_user(
    user_id: str = None,
    email: str = "test@example.com",
    username: str = "testuser",
    is_active: bool = True,
    is_verified: bool = True,
    is_superuser: bool = False,
) -> Mock:
    """Create a mock user for testing."""
    user = Mock(spec=User)
    user.id = UUID(user_id) if user_id else uuid4()
    user.email = email
    user.username = username
    user.full_name = "Test User"
    user.is_active = is_active
    user.is_verified = is_verified
    user.is_superuser = is_superuser
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = None
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)

    # Mock methods
    user.can_login.return_value = is_active and not user.locked_until
    user.increment_failed_attempts = Mock()
    user.reset_failed_attempts = Mock()
    user.set_last_login = Mock()
    user.verify_email = Mock()

    return user


def create_mock_workspace(
    workspace_id: str = None,
    name: str = "Test Workspace",
    owner_id: str = None,
) -> Mock:
    """Create a mock workspace for testing."""
    workspace = Mock(spec=Workspace)
    workspace.id = UUID(workspace_id) if workspace_id else uuid4()
    workspace.name = name
    workspace.description = "Test workspace description"
    workspace.owner_id = UUID(owner_id) if owner_id else uuid4()
    workspace.is_public = False
    workspace.max_members = 10
    workspace.created_at = datetime.now(UTC)
    workspace.updated_at = datetime.now(UTC)

    return workspace


def create_mock_storage_file(
    file_id: str = None,
    workspace_id: str = None,
    user_id: str = None,
    filename: str = "test-file.txt",
) -> Mock:
    """Create a mock storage file for testing."""
    storage_file = Mock(spec=StorageFile)
    storage_file.id = UUID(file_id) if file_id else uuid4()
    storage_file.file_key = f"workspace-{workspace_id or uuid4()}/{filename}"
    storage_file.original_filename = filename
    storage_file.content_type = "text/plain"
    storage_file.file_size = 1024
    storage_file.status = FileStatus.ACTIVE
    storage_file.storage_provider = StorageProvider.MINIO
    storage_file.workspace_id = UUID(workspace_id) if workspace_id else uuid4()
    storage_file.uploaded_by = UUID(user_id) if user_id else uuid4()
    storage_file.metadata = {}
    storage_file.folder_path = "/"
    storage_file.tags = []
    storage_file.is_public = False
    storage_file.created_at = datetime.now(UTC)
    storage_file.updated_at = datetime.now(UTC)

    return storage_file
