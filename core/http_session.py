import asyncio

import aiohttp


class SharedSession:
    _session = None
    _loop = None

    @classmethod
    def get(cls):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        if (
            cls._session is None
            or cls._session.closed
            or cls._loop is not loop
        ):
            if cls._session and not cls._session.closed:
                try:
                    loop.create_task(cls._session.close())
                except Exception:
                    pass
            cls._session = aiohttp.ClientSession()
            cls._loop = loop
        return cls._session

    @classmethod
    async def close(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
        cls._session = None
        cls._loop = None

