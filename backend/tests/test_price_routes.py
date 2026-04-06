from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_realtime_xau_comex():
    r = client.get("/api/realtime/xau/comex")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert "change" in d
    assert d.get("unit") == "USD/oz"


def test_realtime_au_au9999():
    r = client.get("/api/realtime/au/au9999")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert d.get("unit") == "CNY/g"


def test_realtime_fx_yfinance():
    r = client.get("/api/realtime/fx/yfinance")
    assert r.status_code == 200
    d = r.json()
    assert "price" in d
    assert "unit" in d


def test_chart_xau():
    r = client.get("/api/chart/xau?source=comex")
    assert r.status_code == 200
    d = r.json()
    assert "bars" in d
    assert isinstance(d["bars"], list)


def test_chart_au():
    r = client.get("/api/chart/au?source=au9999")
    assert r.status_code == 200
    d = r.json()
    assert "bars" in d
