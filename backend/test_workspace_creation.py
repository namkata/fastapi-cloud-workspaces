import asyncio
import json

import requests


async def test_workspace_creation():
    base_url = "http://localhost:8001/api/v1"

    # Login with correct credentials using form data (OAuth2PasswordRequestForm)
    login_data = {
        "username": "test@example.com",
        "password": "TestPassword123"
    }

    print("Attempting login...")
    login_response = requests.post(f"{base_url}/auth/login", data=login_data)  # Use data, not json
    print(f"Login status: {login_response.status_code}")

    if login_response.status_code == 200:
        login_result = login_response.json()
        token = login_result["token"]["access_token"]
        print(f"Login successful, token: {token[:20]}...")

        # Create workspace
        headers = {"Authorization": f"Bearer {token}"}
        workspace_data = {
            "name": "Test Workspace",
            "description": "A test workspace for debugging"
        }

        print("Attempting workspace creation...")
        workspace_response = requests.post(f"{base_url}/workspaces", json=workspace_data, headers=headers)
        print(f"Workspace creation status: {workspace_response.status_code}")

        if workspace_response.status_code == 201:
            workspace_result = workspace_response.json()
            print(f"Workspace created successfully: {workspace_result}")
        else:
            print(f"Workspace creation failed: {workspace_response.text}")
    else:
        print(f"Login failed: {login_response.text}")

if __name__ == "__main__":
    asyncio.run(test_workspace_creation())
