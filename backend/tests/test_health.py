def test_health_reports_redis_and_database_ok(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["redis"] == "ok"
    assert body["database"] == "ok"