"""
Base database models with common fields and utilities.

This module provides:
- BaseModel with common fields (id, created_at, updated_at)
- Mixins for common functionality
- Utility functions for model operations
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import expression


class Base(DeclarativeBase):
    """Base class for all database models."""

    # Type annotation map for SQLAlchemy 2.0
    type_annotation_map = {
        str: String(255),  # Default string length
    }


class TimestampMixin:
    """Mixin for adding timestamp fields to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the record was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp when the record was last updated",
    )


class UUIDMixin:
    """Mixin for adding UUID primary key to models."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Unique identifier for the record",
    )


class SoftDeleteMixin:
    """Mixin for adding soft delete functionality to models."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Timestamp when the record was soft deleted",
    )

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        doc="Flag indicating if the record is soft deleted",
    )

    def soft_delete(self) -> None:
        """Mark the record as soft deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Base model class with common fields.

    All application models should inherit from this class to get:
    - UUID primary key (id)
    - Created timestamp (created_at)
    - Updated timestamp (updated_at)

    Example:
        class User(BaseModel):
            __tablename__ = "users"

            email: Mapped[str] = mapped_column(String(255), unique=True)
            name: Mapped[str] = mapped_column(String(100))
    """

    __abstract__ = True

    def to_dict(self, exclude: Optional[set] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            exclude: Set of field names to exclude from the dictionary

        Returns:
            Dictionary representation of the model
        """
        exclude = exclude or set()
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name not in exclude
        }

    def update_from_dict(self, data: Dict[str, Any], exclude: Optional[set] = None) -> None:
        """
        Update model instance from dictionary.

        Args:
            data: Dictionary with field names and values
            exclude: Set of field names to exclude from update
        """
        exclude = exclude or {"id", "created_at"}  # Protect immutable fields

        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"


class BaseModelWithSoftDelete(BaseModel, SoftDeleteMixin):
    """
    Base model class with soft delete functionality.

    Inherits all features from BaseModel and adds:
    - Soft delete timestamp (deleted_at)
    - Soft delete flag (is_deleted)
    - Soft delete methods (soft_delete, restore)

    Example:
        class Post(BaseModelWithSoftDelete):
            __tablename__ = "posts"

            title: Mapped[str] = mapped_column(String(200))
            content: Mapped[str] = mapped_column(String)
    """

    __abstract__ = True


class AuditMixin:
    """Mixin for adding audit fields to models."""

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="ID of the user who created the record",
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="ID of the user who last updated the record",
    )


class BaseAuditModel(BaseModel, AuditMixin):
    """
    Base model class with audit fields.

    Inherits all features from BaseModel and adds:
    - Created by user ID (created_by)
    - Updated by user ID (updated_by)

    Example:
        class Document(BaseAuditModel):
            __tablename__ = "documents"

            title: Mapped[str] = mapped_column(String(200))
            content: Mapped[str] = mapped_column(String)
    """

    __abstract__ = True


# Utility functions for working with models

def get_model_fields(model_class: type[BaseModel]) -> set[str]:
    """
    Get all field names for a model class.

    Args:
        model_class: The model class to inspect

    Returns:
        Set of field names
    """
    return {column.name for column in model_class.__table__.columns}


def get_model_relationships(model_class: type[BaseModel]) -> set[str]:
    """
    Get all relationship names for a model class.

    Args:
        model_class: The model class to inspect

    Returns:
        Set of relationship names
    """
    return {rel.key for rel in model_class.__mapper__.relationships}


def model_to_dict(
    instance: BaseModel,
    include_relationships: bool = False,
    exclude: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Convert a model instance to a dictionary.

    Args:
        instance: The model instance to convert
        include_relationships: Whether to include relationship data
        exclude: Set of field names to exclude

    Returns:
        Dictionary representation of the model
    """
    exclude = exclude or set()
    result = {}

    # Add column data
    for column in instance.__table__.columns:
        if column.name not in exclude:
            value = getattr(instance, column.name)
            # Convert datetime to ISO format for JSON serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            # Convert UUID to string for JSON serialization
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value

    # Add relationship data if requested
    if include_relationships:
        for rel in instance.__mapper__.relationships:
            if rel.key not in exclude:
                rel_value = getattr(instance, rel.key)
                if rel_value is not None:
                    if hasattr(rel_value, '__iter__') and not isinstance(rel_value, str):
                        # Handle collections
                        result[rel.key] = [
                            model_to_dict(item, include_relationships=False)
                            for item in rel_value
                        ]
                    else:
                        # Handle single relationships
                        result[rel.key] = model_to_dict(
                            rel_value, include_relationships=False
                        )

    return result
