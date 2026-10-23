"""Lance la rétention à la main : python -m app.jobs.retention [--dry-run]"""

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, engine
from app.services.retention import run_retention
from app.services.storage import S3Storage


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="compte les passages concernés sans agir"
    )
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.app_env, settings.app_log_level)
    async with SessionLocal() as session:
        report = await run_retention(session, S3Storage(settings), settings, dry_run=args.dry_run)
    await engine.dispose()
    print(json.dumps(report.as_dict(), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
