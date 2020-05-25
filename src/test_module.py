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
    assert r.llen("completion_queue") >= 2

    # lastly, check metric table
    status = json.loads(r.execute_command("mantis.status"))
    assert "queue_sizes" in status


def test_heartbeat(redis_conn):
    r = redis_conn

    r.execute_command("FLUSHALL")

    r.execute_command("mantis.add_queue", "h-q1")
    time.sleep(0.5)  # This should makes q1 exceed heartbeat

    r.execute_command("mantis.add_queue", "h-q2")
    r.execute_command("mantis.enqueue", "aaa", time.time(), 4)
    assert r.llen("h-q1") == 0
    assert r.llen("h-q2") == 1

    time.sleep(0.5)  # This should makes q2 exceed heartbeat

    # Now resume the heartbeat for q1
    r.execute_command("mantis.health", "h-q1")
    r.execute_command("mantis.enqueue", "aaa", time.time(), 4)
    assert r.llen("h-q1") == 1
