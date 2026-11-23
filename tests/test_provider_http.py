import io
import json
import threading

from quantstone_data import provider_http


def test_same_provider_allows_only_one_active_request(monkeypatch) -> None:
    state_lock = threading.Lock()
    first_entered = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()
    active = 0
    maximum = 0

    def fake_urlopen(_request, timeout):
        nonlocal active, maximum
        assert timeout == 60
        with state_lock:
            active += 1
            maximum = max(maximum, active)
            is_first = not first_entered.is_set()
            if is_first:
                first_entered.set()
            else:
                second_entered.set()
        if is_first:
            assert release_first.wait(timeout=2)
        with state_lock:
            active -= 1
        return io.BytesIO(json.dumps({"code": 0, "data": {}}).encode())

    monkeypatch.setattr(provider_http, "urlopen", fake_urlopen)
    results: list[dict] = []
    first = threading.Thread(
        target=lambda: results.append(provider_http.post_json("demo", "http://demo", {}))
    )
    second = threading.Thread(
        target=lambda: results.append(provider_http.post_json("demo", "http://demo", {}))
    )
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    assert not second_entered.wait(timeout=0.1)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert maximum == 1
    assert len(results) == 2
