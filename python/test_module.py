import pytest
import redis
import time
import json


@pytest.fixture(scope="session")
def redis_conn():
    r = redis.Redis("0.0.0.0", port=7000, decode_responses=True)
    yield r


def test_health(redis_conn):
    conn = redis_conn
    assert conn.ping()


def test_e2e(redis_conn):
    r = redis_conn

    # Add queue
    r.execute_command("mantis.add_queue", "q1")
    r.execute_command("mantis.add_queue", "q2")

    # Enqueue
    PAYLOAD = "payload"
    r.execute_command("mantis.enqueue", PAYLOAD, time.time(), 1)
    r.execute_command("mantis.enqueue", PAYLOAD, time.time(), 2)

    _, q1_query = r.blpop("q1", timeout=1)
    _, q2_query = r.blpop("q2", timeout=1)
    assert q1_query
    assert q2_query
    assert "_1_lg_sent" in q1_query
    assert "_1_lg_sent" in q2_query

    # some query processing....

    r.execute_command("mantis.complete", q1_query)
    r.execute_command("mantis.complete", q2_query)

    r.execute_command("mantis.drop_queue", "q1")

    # since q1 is dropped, we expect queue 2 has the new query
    r.execute_command("mantis.enqueue", PAYLOAD, time.time(), 3)
    _, q2_query = r.blpop("q2", timeout=1)
    assert q2_query
    assert "_1_lg_sent" in q2_query

    # we completed two queries, see them in completion queue
    assert r.llen("completion_queue") == 2

    # lastly, check metric table
    status = json.loads(r.execute_command("mantis.status"))
    assert "num_active_replica" in status
