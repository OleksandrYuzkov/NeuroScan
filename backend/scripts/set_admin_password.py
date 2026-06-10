#!/usr/bin/env python3
"""
Utility: set/reset a user's password and optionally grant admin role.
Usage: python backend/scripts/set_admin_password.py user@example.com "newpassword" --admin
"""
import sys
import asyncio
from argparse import ArgumentParser
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.auth.security import hash_password
from backend.models.user import User

DATABASE_URL = settings.database_url

async def main():
    p = ArgumentParser()
    p.add_argument("email")
    p.add_argument("password")
    p.add_argument("--admin", action="store_true", help="Set role to admin")
    args = p.parse_args()

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        q = await session.execute(select(User).where(User.email == args.email))
        user = q.scalar_one_or_none()
        if user is None:
            print(f"User not found: {args.email}")
            await engine.dispose()
            return
        hashed = hash_password(args.password)
        user.password_hash = hashed
        if args.admin:
            user.role = "admin"
        session.add(user)
        await session.commit()
        print(f"Updated password for {args.email}. admin={args.admin}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
