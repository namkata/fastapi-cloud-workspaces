"""
Unit tests for DatabaseManager class.

Tests cover:
- Database engine creation and configuration
- Session factory management
- Connection lifecycle
- Health checks
- Table operations
- Session dependency injection
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from app.core.database import (
    DatabaseManager,
    close_db,
    db_manager,
    get_db_session,
    get_db_session_context,
    init_db,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""

    def test_init(self):
        """Test DatabaseManager initialization."""
        manager = DatabaseManager()
        assert manager._engine is None
        assert manager._session_factory is None

    @patch('app.core.database.create_async_engine')
    @patch('app.core.database.get_settings')
    def test_engine_property_creates_engine(self, mock_get_settings, mock_create_engine):
        """Test that engine property creates engine on first access."""
        # Setup
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        mock_settings.debug = False
        mock_settings.is_development = False
        mock_get_settings.return_value = mock_settings

        mock_engine = MagicMock(spec=AsyncEngine)
        mock_engine.sync_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager()

        # Test
        engine = manager.engine

        # Verify
        assert engine == mock_engine
        assert manager._engine == mock_engine
        mock_create_engine.assert_called_once()

    @patch('app.core.database.create_async_engine')
    @patch('app.core.database.get_settings')
    def test_engine_property_returns_existing_engine(self, mock_get_settings, mock_create_engine):
        """Test that engine property returns existing engine on subsequent access."""
        # Setup
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        mock_settings.debug = False
        mock_settings.is_development = False
        mock_get_settings.return_value = mock_settings

        mock_engine = MagicMock(spec=AsyncEngine)
        mock_engine.sync_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager()

        # Test
        engine1 = manager.engine
        engine2 = manager.engine

        # Verify
        assert engine1 == engine2
        assert engine1 == mock_engine
        mock_create_engine.assert_called_once()  # Should only be called once

    @patch('app.core.database.async_sessionmaker')
    def test_session_factory_property_creates_factory(self, mock_sessionmaker):
        """Test that session_factory property creates factory on first access."""
        # Setup
        mock_factory = MagicMock()
        mock_sessionmaker.return_value = mock_factory

        manager = DatabaseManager()
        manager._engine = MagicMock(spec=AsyncEngine)

        # Test
        factory = manager.session_factory

        # Verify
        assert factory == mock_factory
        assert manager._session_factory == mock_factory
        mock_sessionmaker.assert_called_once_with(
            bind=manager._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    @patch('app.core.database.async_sessionmaker')
    def test_session_factory_property_returns_existing_factory(self, mock_sessionmaker):
        """Test that session_factory property returns existing factory on subsequent access."""
        # Setup
        mock_factory = MagicMock()
        mock_sessionmaker.return_value = mock_factory

        manager = DatabaseManager()
        manager._engine = MagicMock(spec=AsyncEngine)

        # Test
        factory1 = manager.session_factory
        factory2 = manager.session_factory

        # Verify
        assert factory1 == factory2
        assert factory1 == mock_factory
        mock_sessionmaker.assert_called_once()  # Should only be called once

    @patch('app.core.database.create_async_engine')
    @patch('app.core.database.get_settings')
    def test_create_engine_with_database_url(self, mock_get_settings, mock_create_engine):
        """Test engine creation with database_url setting."""
        # Setup
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        mock_settings.debug = True
        mock_settings.is_development = True
        mock_get_settings.return_value = mock_settings

        mock_engine = MagicMock(spec=AsyncEngine)
        mock_engine.sync_engine = MagicMock()
        mock_engine.url = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager()

        # Test
        engine = manager._create_engine()

        # Verify
        assert engine == mock_engine
        mock_create_engine.assert_called_once_with(
            url="postgresql+asyncpg://user:pass@localhost:5432/test",
            echo=True,
            echo_pool=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

    @patch('app.core.database.create_async_engine')
    @patch('app.core.database.get_settings')
    def test_create_engine_without_database_url(self, mock_get_settings, mock_create_engine):
        """Test engine creation without database_url setting (fallback to components)."""
        # Setup
        mock_settings = MagicMock()
        mock_settings.database_url = None
        mock_settings.database_user = "testuser"
        mock_settings.database_password = "testpass"
        mock_settings.database_host = "testhost"
        mock_settings.database_port = 5432
        mock_settings.database_name = "testdb"
        mock_settings.debug = False
        mock_settings.is_development = False
        mock_get_settings.return_value = mock_settings

        mock_engine = MagicMock(spec=AsyncEngine)
        mock_engine.sync_engine = MagicMock()
        mock_engine.url = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager()

        # Test
        engine = manager._create_engine()

        # Verify
        expected_url = "postgresql+asyncpg://testuser:testpass@testhost:5432/testdb"
        mock_create_engine.assert_called_once_with(
            url=expected_url,
            echo=False,
            echo_pool=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )

    @pytest.mark.asyncio
    async def test_create_tables_success(self):
        """Test successful table creation."""
        # Setup
        mock_conn = AsyncMock()
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        manager = DatabaseManager()
        manager._engine = mock_engine

        # Test
        await manager.create_tables()

        # Verify
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_drop_tables_success(self):
        """Test successful table dropping."""
        # Setup
        mock_conn = AsyncMock()
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn

        manager = DatabaseManager()
        manager._engine = mock_engine

        # Test
        await manager.drop_tables()

        # Verify
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_engine(self):
        """Test closing database manager with existing engine."""
        # Setup
        mock_engine = AsyncMock(spec=AsyncEngine)
        manager = DatabaseManager()
        manager._engine = mock_engine

        # Test
        await manager.close()

        # Verify
        mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_engine(self):
        """Test closing database manager without existing engine."""
        # Setup
        manager = DatabaseManager()

        # Test (should not raise exception)
        await manager.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        # Setup
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        manager = DatabaseManager()
        manager._session_factory = mock_factory

        # Test
        result = await manager.health_check()

        # Verify
        assert result is True
        mock_session.execute.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        # Setup
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        manager = DatabaseManager()
        manager._session_factory = mock_factory

        # Test
        result = await manager.health_check()

        # Verify
        assert result is False


class TestDatabaseDependencies:
    """Test cases for database dependency functions."""

    @pytest.mark.asyncio
    async def test_get_db_session_success(self):
        """Test successful database session dependency."""
        # Setup
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch.object(db_manager, 'session_factory', mock_factory):
            # Test
            async_gen = get_db_session()
            session = await async_gen.__anext__()

            # Verify
            assert session == mock_session

            # Test cleanup
            try:
                await async_gen.__anext__()
            except StopAsyncIteration:
                pass

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_with_exception(self):
        """Test database session dependency with exception."""
        # Setup
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch.object(db_manager, 'session_factory', mock_factory):
            # Test
            async_gen = get_db_session()
            session = await async_gen.__anext__()

            # Simulate exception during session use
            with pytest.raises(ValueError):
                try:
                    raise ValueError("Test error")
                except ValueError:
                    await async_gen.athrow(ValueError, ValueError("Test error"), None)

            # Verify rollback was called
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_context(self):
        """Test database session context function."""
        # Setup
        mock_factory = MagicMock()

        with patch.object(db_manager, 'session_factory', mock_factory):
            # Test
            result = await get_db_session_context()

            # Verify
            assert result == mock_factory.return_value


class TestDatabaseInitialization:
    """Test cases for database initialization functions."""

    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Test successful database initialization."""
        # Setup
        with patch.object(db_manager, 'health_check', return_value=True) as mock_health:
            # Test
            await init_db()

            # Verify
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_health_check_failure(self):
        """Test database initialization with health check failure."""
        # Setup
        with patch.object(db_manager, 'health_check', return_value=False) as mock_health:
            # Test
            with pytest.raises(RuntimeError, match="Database health check failed"):
                await init_db()

            # Verify
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_exception(self):
        """Test database initialization with exception."""
        # Setup
        with patch.object(db_manager, 'health_check', side_effect=Exception("Test error")) as mock_health:
            # Test
            with pytest.raises(Exception, match="Test error"):
                await init_db()

            # Verify
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db(self):
        """Test database closure function."""
        # Setup
        with patch.object(db_manager, 'close') as mock_close:
            # Test
            await close_db()

            # Verify
            mock_close.assert_called_once()


class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full database manager lifecycle."""
        # Setup
        with patch('app.core.database.create_async_engine') as mock_create_engine, \
             patch('app.core.database.async_sessionmaker') as mock_sessionmaker, \
             patch('app.core.database.get_settings') as mock_get_settings:

            # Configure mocks
            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
            mock_settings.debug = False
            mock_settings.is_development = False
            mock_get_settings.return_value = mock_settings

            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_engine.sync_engine = MagicMock()
            mock_engine.url = MagicMock()
            mock_create_engine.return_value = mock_engine

            mock_factory = MagicMock()
            mock_sessionmaker.return_value = mock_factory

            mock_session = AsyncMock(spec=AsyncSession)
            mock_factory.return_value.__aenter__.return_value = mock_session

            manager = DatabaseManager()

            # Test engine creation
            engine = manager.engine
            assert engine == mock_engine

            # Test session factory creation
            factory = manager.session_factory
            assert factory == mock_factory

            # Test health check
            result = await manager.health_check()
            assert result is True
            mock_session.execute.assert_called_with("SELECT 1")

            # Test close
            await manager.close()
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_dependency_full_cycle(self):
        """Test complete session dependency cycle."""
        # Setup
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch.object(db_manager, 'session_factory', mock_factory):
            # Test normal flow
            session_gen = get_db_session()
            session = await session_gen.__anext__()

            assert session == mock_session

            # Complete the generator
            try:
                await session_gen.__anext__()
            except StopAsyncIteration:
                pass

            # Verify session lifecycle
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_engine_access(self):
        """Test concurrent access to engine property."""
        # Setup
        with patch('app.core.database.create_async_engine') as mock_create_engine, \
             patch('app.core.database.get_settings') as mock_get_settings:

            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
            mock_settings.debug = False
            mock_settings.is_development = False
            mock_get_settings.return_value = mock_settings

            mock_engine = MagicMock(spec=AsyncEngine)
            mock_engine.sync_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            manager = DatabaseManager()

            # Test concurrent access
            async def get_engine():
                return manager.engine

            engines = await asyncio.gather(
                get_engine(),
                get_engine(),
                get_engine()
            )

            # Verify all engines are the same instance
            assert all(engine == mock_engine for engine in engines)
            # Engine should only be created once
            mock_create_engine.assert_called_once()
