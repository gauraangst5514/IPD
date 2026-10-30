"""Create synthetic local demonstration accounts without public role escalation."""
import asyncio
import json
from pathlib import Path
import secrets
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def main():
    from sqlalchemy import select
    from app.core.database import create_tables, async_session
    from app.core.auth import hash_password
    from app.models import User, Vehicle, Claim, ClaimImage, ClaimAssessment, FraudFlag
    from app.models.user import UserRole
    await create_tables()
    destination = Path(os.environ.get("DEMO_ACCOUNTS_PATH",str(ROOT / "var" / "demo_accounts.json")))
    destination.parent.mkdir(exist_ok=True)
    credentials = json.loads(destination.read_text()) if destination.exists() else {}
    async with async_session() as db:
        for role in (UserRole.CLAIMANT, UserRole.ASSESSOR, UserRole.ADMIN):
            email = f"{role.value}@intelliclaim.test"
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not user:
                password = secrets.token_urlsafe(16)
                user = User(email=email, full_name=f"Demo {role.value.title()}",
                            hashed_password=hash_password(password), role=role)
                db.add(user)
                await db.flush()
                credentials[role.value] = {"email": email, "password": password}
        await db.commit()
    destination.write_text(json.dumps(credentials, indent=2) + "\n")
    destination.chmod(0o600)
    print("Demo accounts ready. Login credentials: var/demo_accounts.json")


if __name__ == "__main__":
    asyncio.run(main())
