"""Bound the request before multipart parsing, including chunked requests."""
from starlette.responses import JSONResponse


class RequestTooLarge(Exception):
    pass


class RequestSizeLimit:
    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            content_length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, 400)(scope, receive, send)
        if content_length > self.max_bytes:
            return await JSONResponse({'detail': 'Request exceeds byte limit'}, 413)(scope, receive, send)
        size = 0
        exceeded = False
        started = False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message['type'] == 'http.request':
                size += len(message.get('body', b''))
                if size > self.max_bytes:
                    exceeded = True
                    raise RequestTooLarge()
            return message

        async def guarded_send(message):
            nonlocal started
            if exceeded:
                return
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not started:
            await JSONResponse({'detail': 'Request exceeds byte limit'}, 413)(scope, receive, send)
