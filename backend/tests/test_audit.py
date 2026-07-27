"""Tests for POST /api/audit."""
import httpx
import respx


SAMPLE_HTML = """
<html>
  <head>
    <title>Example Domain</title>
    <meta name="description" content="This domain is for use in examples.">
  </head>
  <body><h1>Example</h1></body>
</html>
"""


@respx.mock
def test_valid_url_returns_audit_data(client):
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "server": "ExampleServer",
            },
            text=SAMPLE_HTML,
        )
    )

    response = client.post("/api/audit", json={"url": "https://example.com/"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["url"] == "https://example.com/"
    assert data["status_code"] == 200
    assert data["https"] is True
    assert data["title"] == "Example Domain"
    assert data["meta_description"] == "This domain is for use in examples."
    assert data["server"] == "ExampleServer"
    assert data["cached"] is False
    assert data["response_time_ms"] >= 0


def test_invalid_url_returns_structured_error(client):
    response = client.post("/api/audit", json={"url": "not-a-url"})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_URL"
    assert "message" in body["error"]


def test_missing_url_field_returns_validation_error(client):
    response = client.post("/api/audit", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@respx.mock
def test_timeout_returns_structured_timeout_error(client):
    respx.get("https://slow.example.com/").mock(side_effect=httpx.TimeoutException("timed out"))

    response = client.post("/api/audit", json={"url": "https://slow.example.com/"})

    assert response.status_code == 504
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TIMEOUT"


@respx.mock
def test_repeat_request_within_ttl_is_served_from_cache(client):
    route = respx.get("https://cached.example.com/").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=SAMPLE_HTML,
        )
    )

    first = client.post("/api/audit", json={"url": "https://cached.example.com/"})
    second = client.post("/api/audit", json={"url": "https://cached.example.com/"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["cached"] is False
    assert second.json()["data"]["cached"] is True
    # The upstream server should only have been hit once - the second
    # response was served entirely from cache.
    assert route.call_count == 1
