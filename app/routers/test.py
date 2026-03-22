from starlette.responses import PlainTextResponse


async def test_endpoint(_: object) -> PlainTextResponse:
    return PlainTextResponse("running")
