"""Run with PYTHONPATH containing the built TracyServerBindings:
    python -m pytest extra/mcp/test_disconnect_reason.py
"""
import types

import tracy_mcp

CLOSE = tracy_mcp.tracy_server.close_reasons
MB = 1024 * 1024


class FakeWorker:
    def __init__(self, connected, code, limit=0, growth=0, last_type=27):
        self._c, self._code, self._limit, self._growth = connected, code, limit, growth
        self._last_type = last_type

    def is_connected(self):
        return self._c

    def get_close_reason(self):
        return self._code

    def get_last_queue_type(self):
        return self._last_type

    def get_memory_limit(self):
        return self._limit

    def get_memory_growth(self):
        return self._growth


def inst(worker, path=None):
    return types.SimpleNamespace(worker=worker, path=path)


def test_connected_has_no_reason():
    assert tracy_mcp._disconnect_reason(inst(FakeWorker(True, 0))) is None


def test_file_capture_has_no_reason():
    assert tracy_mcp._disconnect_reason(inst(FakeWorker(False, CLOSE["socket_closed"]), path="x.tracy")) is None


def test_socket_close():
    r = tracy_mcp._disconnect_reason(inst(FakeWorker(False, CLOSE["socket_closed"])))
    assert "socket closed" in r and "27" in r


def test_memory_limit_reports_cap_and_growth():
    r = tracy_mcp._disconnect_reason(inst(FakeWorker(False, CLOSE["memory_limit"], 3072 * MB, 5000 * MB)))
    assert "cap 3072 MB" in r and "grew 5000 MB" in r


def test_no_queue_item_yet_omits_last_type():
    last_type = tracy_mcp.tracy_server.no_queue_type
    r = tracy_mcp._disconnect_reason(inst(FakeWorker(False, CLOSE["socket_closed"], last_type=last_type)))
    assert "last queue item type" not in r
