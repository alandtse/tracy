"""Run with PYTHONPATH containing the built TracyServerBindings:
    python -m pytest extra/mcp/test_stream_info.py
"""
import types

import tracy_mcp

CLOSE = tracy_mcp.tracy_server.close_reasons
MB = 1024 * 1024
S = 1_000_000_000


class FakeWorker:
    def __init__(self, connected, seconds, growth_mb, limit_mb=0, code=0):
        self._c, self._code = connected, code
        self._first, self._last = 5 * S, 5 * S + int(seconds * S)
        self._growth, self._limit = growth_mb * MB, limit_mb * MB

    def is_connected(self):
        return self._c

    def get_first_time(self):
        return self._first

    def get_last_time(self):
        return self._last

    def get_memory_growth(self):
        return self._growth

    def get_memory_limit(self):
        return self._limit

    def get_close_reason(self):
        return self._code

    def get_last_queue_type(self):
        return tracy_mcp.tracy_server.no_queue_type


def inst(worker, path=None):
    return types.SimpleNamespace(worker=worker, path=path)


def test_file_capture_has_no_stream_info():
    assert tracy_mcp._stream_info(inst(FakeWorker(True, 10, 100), path="x.tracy")) == {}


def test_rate_and_time_to_cap_while_connected():
    info = tracy_mcp._stream_info(inst(FakeWorker(True, 10, 1000, limit_mb=3000)))
    assert info == {"data_seconds": 10.0, "stream_mb_per_s": 100.0, "seconds_to_cap": 20.0}


def test_no_time_to_cap_without_a_cap():
    info = tracy_mcp._stream_info(inst(FakeWorker(True, 10, 1000)))
    assert "seconds_to_cap" not in info and info["stream_mb_per_s"] == 100.0


def test_no_time_to_cap_after_disconnect():
    info = tracy_mcp._stream_info(inst(FakeWorker(False, 10, 3000, limit_mb=3000, code=CLOSE["memory_limit"])))
    assert "seconds_to_cap" not in info and info["data_seconds"] == 10.0


def test_empty_stream_has_no_rate():
    assert tracy_mcp._stream_info(inst(FakeWorker(True, 0, 0, limit_mb=3000))) == {"data_seconds": 0.0}


def test_save_extra_reports_the_cap_cutoff():
    w = FakeWorker(False, 25.6, 3000, limit_mb=3000, code=CLOSE["memory_limit"])
    extra = tracy_mcp._save_extra(inst(w))
    assert extra["connected"] is False
    assert "memory limit" in extra["disconnect_reason"]
    assert extra["data_seconds"] == 25.6


def test_save_extra_is_empty_for_file_captures():
    assert tracy_mcp._save_extra(inst(FakeWorker(True, 1, 1), path="x.tracy")) == {}
