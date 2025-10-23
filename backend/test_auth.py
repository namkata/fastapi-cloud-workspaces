import asyncio
import sys

sys.path.append('.')

from app.core.database import get_db_session
from app.modules.auth.service import AuthService


async def test_authentication():
    async for db in get_db_session():
        auth_service = AuthService(db)

        # Test with existing user
        user = await auth_service.get_user_by_username_or_email('test@example.com')
        print(f'User found: {user is not None}')
        if user:
            print(f'User ID: {user.id}')
            print(f'Username: {user.username}')
            print(f'Email: {user.email}')

            # Try different passwords to see what works
            passwords = ['testpassword', 'password', 'test123', 'TestPassword123']
            for pwd in passwords:
                auth_user = await auth_service.authenticate_user('test@example.com', pwd)
                print(f'Password "{pwd}": {auth_user is not None}')
                if auth_user:
                    print(f'  Authenticated user ID: {auth_user.id}')
                    break
        break

if __name__ == "__main__":
    asyncio.run(test_authentication())
