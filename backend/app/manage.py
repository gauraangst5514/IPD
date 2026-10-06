"""Local administrative provisioning; passwords are read from the terminal, never argv."""
import argparse
import asyncio
import getpass
from sqlalchemy import select
from app.core.database import async_session, engine
from app.core.auth import hash_password
from app.models.user import User, UserRole
from app.api.auth import RegisterRequest


async def main(args):
    try:
        async with async_session() as db:
            user = (await db.execute(select(User).where(User.email == args.email))).scalar_one_or_none()
            if args.action == 'revoke-sessions':
                if user is None:
                    raise SystemExit('User not found')
                user.token_version += 1
            else:
                if user is not None:
                    raise SystemExit('User already exists; no changes made')
                password = getpass.getpass('New account password (12–72 UTF-8 bytes): ')
                if password != getpass.getpass('Confirm password: '):
                    raise SystemExit('Passwords do not match')
                request = RegisterRequest(email=args.email, password=password, full_name=args.name)
                db.add(User(email=request.email, full_name=request.full_name,
                            hashed_password=hash_password(password), role=UserRole(args.role)))
            await db.commit()
            print('Account operation completed')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create-user', 'revoke-sessions'])
    parser.add_argument('--email', required=True)
    parser.add_argument('--role', choices=['claimant', 'assessor', 'admin'], default='claimant')
    parser.add_argument('--name', default='')
    asyncio.run(main(parser.parse_args()))
