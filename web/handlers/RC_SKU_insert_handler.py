from aiohttp import web
import logging

from ..middlewares import middleware, semaphore

logger = logging.getLogger(__name__)

@middleware(semaphore(10, 10))
async def handler(request: web.Request) -> web.Response:
    logger.debug("RC SKU insert handler called")
    return web.Response(text='OK')