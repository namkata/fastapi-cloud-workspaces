#!/usr/bin/env python3
"""
Initialize workspace roles in the database.

This script creates the default workspace roles (ADMIN, EDITOR, VIEWER)
that are required for workspace functionality.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from app.core.database import get_db_session
from sqlalchemy import text


async def init_workspace_roles():
    """Initialize default workspace roles."""

    # First, we need to create a dummy workspace to satisfy the foreign key constraint
    # In a real scenario, roles would be created per workspace

    async for db in get_db_session():
        try:
            # Check if roles already exist
            result = await db.execute(text("SELECT COUNT(*) FROM workspace_roles"))
            count = result.scalar()

            if count > 0:
                print(f"Workspace roles already exist ({count} roles found)")
                return

            # Check if we have any workspaces to attach roles to
            result = await db.execute(text("SELECT id FROM workspaces LIMIT 1"))
            workspace_row = result.fetchone()

            if not workspace_row:
                print("No workspaces found. Creating a dummy workspace first...")
                # Create a dummy workspace for system roles
                dummy_workspace_id = str(uuid.uuid4())

                # Get a user to be the owner (use the first user)
                result = await db.execute(text("SELECT id FROM users LIMIT 1"))
                user_row = result.fetchone()

                if not user_row:
                    print("No users found. Cannot create workspace roles without a workspace owner.")
                    return

                now = datetime.now(timezone.utc)
                await db.execute(text("""
                    INSERT INTO workspaces
                    (id, name, description, status, owner_id, created_at, updated_at)
                    VALUES (:id, :name, :description, :status, :owner_id, :created_at, :updated_at)
                """), {
                    "id": dummy_workspace_id,
                    "name": "System Workspace",
                    "description": "System workspace for default roles",
                    "status": "active",
                    "owner_id": user_row[0],
                    "created_at": now,
                    "updated_at": now,
                })
                workspace_id = dummy_workspace_id
            else:
                workspace_id = workspace_row[0]

            # Create default roles using the actual database schema
            now = datetime.now(timezone.utc)

            roles_data = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "admin",
                    "description": "Full access to workspace management and content",
                    "permissions": json.dumps({
                        "can_read": True,
                        "can_write": True,
                        "can_admin": True,
                        "can_invite": True,
                        "can_remove_members": True,
                    }),
                    "is_system_role": True,
                    "workspace_id": workspace_id,
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "editor",
                    "description": "Can read and write workspace content",
                    "permissions": json.dumps({
                        "can_read": True,
                        "can_write": True,
                        "can_admin": False,
                        "can_invite": False,
                        "can_remove_members": False,
                    }),
                    "is_system_role": True,
                    "workspace_id": workspace_id,
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "viewer",
                    "description": "Read-only access to workspace content",
                    "permissions": json.dumps({
                        "can_read": True,
                        "can_write": False,
                        "can_admin": False,
                        "can_invite": False,
                        "can_remove_members": False,
                    }),
                    "is_system_role": True,
                    "workspace_id": workspace_id,
                    "created_at": now,
                    "updated_at": now,
                },
            ]

            # Insert roles using raw SQL
            for role_data in roles_data:
                await db.execute(text("""
                    INSERT INTO workspace_roles
                    (id, name, description, permissions, is_system_role, workspace_id, created_at, updated_at)
                    VALUES (:id, :name, :description, :permissions, :is_system_role, :workspace_id, :created_at, :updated_at)
                """), role_data)

            await db.commit()
            print(f"Successfully created {len(roles_data)} workspace roles")

            # Verify creation
            result = await db.execute(text("SELECT name, description FROM workspace_roles WHERE is_system_role = true"))
            created_roles = result.fetchall()
            print("Created system roles:")
            for role in created_roles:
                print(f"  - {role[0]}: {role[1]}")

        except Exception as e:
            await db.rollback()
            print(f"Error initializing workspace roles: {e}")
            raise
        finally:
            await db.close()
            break


if __name__ == "__main__":
    asyncio.run(init_workspace_roles())
