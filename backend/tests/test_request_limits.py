import pytest
from shared.request_limits import RequestSizeLimit


@pytest.mark.asyncio
@pytest.mark.parametrize('declared', [False, True])
async def test_request_limit_before_or_during_body(declared):
    sent = []
    messages = iter([{'type':'http.request', 'body':b'1234', 'more_body':True},
                     {'type':'http.request', 'body':b'5678', 'more_body':False}])
    async def receive():
        return next(messages)
    async def send(message):
        sent.append(message)
    async def app(scope, receive, send):
        while (await receive()).get('more_body'):
            pass
        raise AssertionError('Oversized body reached handler')
    await RequestSizeLimit(app, 5)({'type':'http', 'headers':[(b'content-length', b'8')] if declared else []}, receive, send)
    assert sent[0]['status'] == 413
