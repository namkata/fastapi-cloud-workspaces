#!/usr/bin/env python3
"""
Test script for workspace management system.

This script tests the workspace management endpoints and functionality.
"""
import asyncio
import json
from typing import Any, Dict

import httpx
from httpx import AsyncClient


class WorkspaceSystemTester:
    """Test class for workspace management system."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.auth_token = None
        self.workspace_id = None
        self.user_id = None

    async def test_auth_flow(self, client: AsyncClient) -> bool:
        """Test authentication flow."""
        print("🔐 Testing authentication flow...")

        # Test user registration
        register_data = {
            "email": "workspace_test@example.com",
            "username": "workspace_test",
            "password": "TestPassword123!",
            "confirm_password": "TestPassword123!",
            "full_name": "Workspace Test User"
        }

        try:
            response = await client.post("/api/v1/auth/register", json=register_data)
            if response.status_code in [200, 201]:
                print("✅ User registration successful")
                user_data = response.json()
                # Handle both direct user data and nested user data
                if "user" in user_data:
                    self.user_id = user_data["user"].get("id")
                else:
                    self.user_id = user_data.get("id")
            elif response.status_code == 400 and "already exists" in response.text:
                print("ℹ️  User already exists, proceeding with login")
            else:
                print(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False

        # Test user login
        login_data = {
            "username": "workspace_test",
            "password": "TestPassword123!"
        }

        try:
            response = await client.post("/api/v1/auth/login", data=login_data)
            if response.status_code == 200:
                token_data = response.json()
                # Handle nested token structure
                if "token" in token_data:
                    self.auth_token = token_data["token"].get("access_token")
                else:
                    self.auth_token = token_data.get("access_token")
                print("✅ User login successful")
                return True
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {self.auth_token}"}

    async def test_workspace_creation(self, client: AsyncClient) -> bool:
        """Test workspace creation."""
        print("\n🏢 Testing workspace creation...")

        workspace_data = {
            "name": "Test Workspace",
            "description": "A test workspace for development"
        }

        try:
            response = await client.post(
                "/api/v1/workspaces",
                json=workspace_data,
                headers=self.get_auth_headers()
            )

            if response.status_code == 201:
                workspace = response.json()
                self.workspace_id = workspace.get("id")
                print(f"✅ Workspace created successfully: {workspace['name']}")
                print(f"   ID: {self.workspace_id}")
                return True
            else:
                print(f"❌ Workspace creation failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Workspace creation error: {e}")
            return False

    async def test_workspace_listing(self, client: AsyncClient) -> bool:
        """Test workspace listing."""
        print("\n📋 Testing workspace listing...")

        try:
            response = await client.get(
                "/api/v1/workspaces",
                headers=self.get_auth_headers()
            )

            if response.status_code == 200:
                workspaces = response.json()
                print(f"✅ Retrieved {len(workspaces)} workspaces")
                for ws in workspaces:
                    print(f"   - {ws['name']} ({ws['id']})")
                return True
            else:
                print(f"❌ Workspace listing failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Workspace listing error: {e}")
            return False

    async def test_workspace_details(self, client: AsyncClient) -> bool:
        """Test workspace details retrieval."""
        print("\n🔍 Testing workspace details...")

        if not self.workspace_id:
            print("❌ No workspace ID available for testing")
            return False

        try:
            headers = self.get_auth_headers()
            headers["X-Workspace-ID"] = self.workspace_id

            response = await client.get(
                f"/api/v1/workspaces/{self.workspace_id}",
                headers=headers
            )

            if response.status_code == 200:
                workspace = response.json()
                print(f"✅ Workspace details retrieved: {workspace['name']}")
                print(f"   Status: {workspace['status']}")
                print(f"   Members: {len(workspace.get('members', []))}")
                return True
            else:
                print(f"❌ Workspace details failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Workspace details error: {e}")
            return False

    async def test_workspace_context_isolation(self, client: AsyncClient) -> bool:
        """Test workspace context isolation."""
        print("\n🔒 Testing workspace context isolation...")

        if not self.workspace_id:
            print("❌ No workspace ID available for testing")
            return False

        # Test with correct workspace ID
        try:
            headers = self.get_auth_headers()
            headers["X-Workspace-ID"] = self.workspace_id

            response = await client.get(
                "/api/v1/workspaces",
                headers=headers
            )

            if response.status_code == 200:
                print("✅ Request with valid workspace ID succeeded")
            else:
                print(f"❌ Request with valid workspace ID failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Workspace context test error: {e}")
            return False

        # Test with invalid workspace ID format
        try:
            headers = self.get_auth_headers()
            headers["X-Workspace-ID"] = "invalid-uuid"

            response = await client.get(
                "/api/v1/workspaces",
                headers=headers
            )

            if response.status_code == 400:
                print("✅ Request with invalid workspace ID properly rejected")
                return True
            else:
                print(f"❌ Request with invalid workspace ID should have been rejected: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Invalid workspace ID test error: {e}")
            return False

    async def test_workspace_update(self, client: AsyncClient) -> bool:
        """Test workspace update."""
        print("\n✏️ Testing workspace update...")

        if not self.workspace_id:
            print("❌ No workspace ID available for testing")
            return False

        update_data = {
            "name": "Updated Test Workspace",
            "description": "Updated description for the test workspace"
        }

        try:
            headers = self.get_auth_headers()
            headers["X-Workspace-ID"] = self.workspace_id

            response = await client.put(
                f"/api/v1/workspaces/{self.workspace_id}",
                json=update_data,
                headers=headers
            )

            if response.status_code == 200:
                workspace = response.json()
                print(f"✅ Workspace updated successfully: {workspace['name']}")
                return True
            else:
                print(f"❌ Workspace update failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Workspace update error: {e}")
            return False

    async def run_all_tests(self) -> None:
        """Run all workspace system tests."""
        print("🚀 Starting Workspace Management System Tests\n")

        async with AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            # Test authentication first
            if not await self.test_auth_flow(client):
                print("\n❌ Authentication tests failed. Cannot proceed with workspace tests.")
                return

            # Test workspace operations
            tests = [
                self.test_workspace_creation,
                self.test_workspace_listing,
                self.test_workspace_details,
                self.test_workspace_context_isolation,
                self.test_workspace_update,
            ]

            passed = 0
            total = len(tests)

            for test in tests:
                try:
                    if await test(client):
                        passed += 1
                    else:
                        print(f"❌ Test {test.__name__} failed")
                except Exception as e:
                    print(f"❌ Test {test.__name__} error: {e}")

            print(f"\n📊 Test Results: {passed}/{total} tests passed")

            if passed == total:
                print("🎉 All workspace management tests passed!")
            else:
                print("⚠️  Some tests failed. Check the output above for details.")


async def main():
    """Main test function."""
    tester = WorkspaceSystemTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
