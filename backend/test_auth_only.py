#!/usr/bin/env python3
"""
Simple authentication test script for FastAPI Cloud Workspaces.

This script tests only the authentication endpoints without workspace context.
"""
import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict

import httpx
from structlog import get_logger

logger = get_logger(__name__)

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api/v1"

# Test user data
TEST_USER = {
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User"
}


async def test_health_check() -> bool:
    """Test the health check endpoint."""
    print("🔍 Testing health check...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False


async def test_user_registration() -> tuple[bool, dict]:
    """Test user registration endpoint."""
    print("🔍 Testing user registration...")

    registration_data = {
        "email": f"user{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com",
        "username": f"user{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "password": "TestPassword123",
        "confirm_password": "TestPassword123",
        "full_name": "Dynamic Test User"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/auth/register",
                json=registration_data
            )

        print(f"Registration response status: {response.status_code}")
        print(f"Registration response headers: {dict(response.headers)}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Registration successful: {data.get('message')}")
            return True, data
        else:
            print(f"❌ Registration failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
            return False, {}

    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        return False, {}


async def test_user_login(username: str = "testuser", password: str = "TestPassword123") -> tuple[bool, dict]:
    """Test user login."""
    print("🔍 Testing user login...")

    login_data = {
        "username": username,
        "password": password
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/auth/login",
                data=login_data,  # OAuth2PasswordRequestForm expects form data
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

        print(f"Login response status: {response.status_code}")
        print(f"Login response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Login successful: {data.get('message', 'Login completed')}")
            return True, data
        else:
            print(f"❌ Login failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
            return False, {}

    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return False, {}


async def test_protected_endpoint(access_token: str) -> bool:
    """Test accessing a protected endpoint."""
    print("🔍 Testing protected endpoint access...")

    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/auth/me",
                headers=headers
            )

        print(f"Protected endpoint response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Protected endpoint access successful")
            print(f"   User ID: {data.get('id')}")
            print(f"   Email: {data.get('email')}")
            print(f"   Full name: {data.get('full_name')}")
            return True
        else:
            print(f"❌ Protected endpoint access failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Raw response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Protected endpoint error: {str(e)}")
        return False


async def main():
    """Main test function."""
    print("🚀 Starting FastAPI Authentication Tests")
    print("=" * 50)

    # Test health endpoint
    health_ok = await test_health_check()
    if not health_ok:
        print("❌ Health check failed. Exiting.")
        return

    # Test user registration
    registration_success, registration_data = await test_user_registration()
    if not registration_success:
        print("❌ Registration failed. Exiting.")
        return

    # Extract user data for login test
    user_data = registration_data.get("user", {})

    # Test user login
    login_success, login_data = await test_user_login("testuser", "TestPassword123")
    if not login_success:
        print("❌ Login failed. Exiting.")
        return

    # Test protected endpoint
    access_token = login_data.get("access_token")
    if access_token:
        await test_protected_endpoint(access_token)

    print("\n" + "=" * 50)
    print("✅ All authentication tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
