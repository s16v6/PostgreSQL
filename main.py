import asyncio

from misc.settings import settings
from database import Database

async def main():
    db = Database(settings.database_url)

    while True:
        await asyncio.sleep(3600)


if __name__=='__main__':
    asyncio.run(main())