import asyncio

from misc.settings import settings
from database import Database
from database.models import register_models
from web import Server, Route
from web.handlers import RC_SKU_insert_handler, RC_SKU_get_handler
from web.handlers import RC_SKU_Margin_insert_handler

async def main():
    db = Database(settings.database_url)

    await register_models()

    await db.create_tables()

    insert_route = Route('GET', '/v1/RC_SKU/insert', RC_SKU_insert_handler.handler)
    get_route = Route('GET', '/v1/RC_SKU/get', RC_SKU_get_handler.handler)
    margin_insert_route = Route('GET', '/v1/RC_SKU_Margin/insert', RC_SKU_Margin_insert_handler.handler)
    # margin_get_route = Route('GET', '/v1/RC_SKU_Margin/get', RC_SKU_Margin_get_handler.handler)


    server = Server('localhost', 8000, 
                    [insert_route, 
                     get_route,
                     margin_insert_route,
                    #  margin_get_route
                     ])

    server.app['db'] = db

    await server.start()

    while True:
        await asyncio.sleep(3600)


if __name__=='__main__':
    asyncio.run(main())