"""Tests for IP-based rate limiting.

The test environment configures RATE_LIMIT_DEFAULT=3/minute (see
conftest.py) so this test completes quickly without waiting an hour.
"""
import httpx
import respx


@respx.mock
def test_requests_beyond_limit_receive_429(client):
    respx.get("https://ratelimit.example.com/").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")
    )

    statuses = []
    for _ in range(4):
        response = client.post("/api/audit", json={"url": "https://ratelimit.example.com/"})
        statuses.append(response.status_code)

    assert 429 in statuses
    limited_response = [r for r in statuses if r == 429][0]
    assert limited_response == 429
