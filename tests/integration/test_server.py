"""The HTTP surface: routes, headers, limits, and the static page."""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request

import pytest

from redlens.config import Config
from redlens.server import build_server
from support import RETURNED, SENT, docx


@pytest.fixture
def base_url():
    server = build_server(Config(port=0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, response.read(), dict(response.headers)


def post(url, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def documents():
    return {"before": base64.b64encode(docx(SENT)).decode("ascii"),
            "before_name": "sent.docx",
            "after": base64.b64encode(docx(RETURNED)).decode("ascii"),
            "after_name": "returned.docx"}


def test_the_page_is_served(base_url):
    status, body, headers = get(base_url + "/")
    assert status == 200
    assert b"<title>Redlens" in body
    assert headers["Content-Type"].startswith("text/html")


def test_the_assets_are_served(base_url):
    for path, marker in (("/styles.css", b"--paper"), ("/app.js", b"compareNow")):
        status, body, _ = get(base_url + path)
        assert status == 200
        assert marker in body


def test_health(base_url):
    status, body, _ = get(base_url + "/api/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_security_headers_forbid_outbound_traffic(base_url):
    _, _, headers = get(base_url + "/")
    policy = headers["Content-Security-Policy"]
    assert "connect-src 'self'" in policy
    assert "default-src 'self'" in policy
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"


def test_compare_over_http(base_url):
    status, body = post(base_url + "/api/compare", documents())
    assert status == 200
    assert body["summary"]["changes"] > 0


def test_note_over_http(base_url):
    _, compared = post(base_url + "/api/compare", documents())
    liability = next(c for c in compared["changes"] if c["clause"] == "9.2")
    body = documents()
    body["queried"] = [liability["index"]]
    status, reply = post(base_url + "/api/note", body)
    assert status == 200
    assert "Clause 9.2" in reply["note"]


def test_an_unknown_api_route_is_404_not_the_page(base_url):
    status, body = post(base_url + "/api/nonsense", {})
    assert status == 404
    assert "error" in body


def test_a_missing_asset_is_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(base_url + "/nowhere.css")
    assert caught.value.code == 404


def test_path_traversal_is_refused(base_url):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(base_url + "/../src/redlens/server.py")
    assert caught.value.code in (400, 403, 404)


def test_broken_json_is_refused_clearly(base_url):
    request = urllib.request.Request(
        base_url + "/api/compare", data=b"{not json",
        method="POST", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=10)
    assert caught.value.code == 400


def test_the_server_binds_only_the_loopback_by_default():
    assert Config().host == "127.0.0.1"
