import asyncio

from misc.settings import settings
from database import Database
from database.models import register_models
from web import Server, Route
from web.handlers import RC_SKU_insert_handler

async def main():
    db = Database(settings.database_url)

    insert_route = Route('GET', '/insert', RC_SKU_insert_handler.handler)

    server = Server('localhost', 8000, [insert_route])

    server.app['db'] = db

    await server.start()

    await register_models()

    await db.create_tables()

    while True:
        await asyncio.sleep(3600)


if __name__=='__main__':
    asyncio.run(main())