import asyncio

from misc.settings import settings
from database import Database
from database.models import register_models

async def main():
    db = Database(settings.database_url)

    await register_models()

    await db.create_tables()

    while True:
        await asyncio.sleep(3600)


if __name__=='__main__':
    asyncio.run(main())