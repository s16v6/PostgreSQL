from aiohttp import web
from asyncio import sleep
import logging

from ..middlewares import middleware, semaphore

logger = logging.getLogger(__name__)

@middleware(semaphore(10, 10))
async def ping_handler(request: web.Request) -> web.Response:
    logger.debug("Ping handler called")
    return web.Response(text='OK')