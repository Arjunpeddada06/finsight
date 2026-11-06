from app.ratelimit import limiter


async def test_upload_is_rate_limited_per_minute(client):
    limiter.reset()
    limiter.enabled = True
    try:
        codes = [(await client.post("/api/documents/upload", files={"file": ("a.txt", b"x", "text/plain")})).status_code for _ in range(22)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:20] == [415] * 20  # first 20 reach validation
    assert codes[20:] == [429, 429]  # the 21st and 22nd are refused
