"""Run with PYTHONPATH containing the built TracyServerBindings:
    python -m pytest extra/mcp/test_memory_budget.py
"""
import tracy_mcp

MB = 1024 * 1024


class FakeWorker:
    def __init__(self, memory, connected=None, ledger=None):
        self.memory = memory
        self.connected = connected
        self.ledger = ledger

    def is_connected(self):
        return self.connected

    def shutdown(self):
        if self.ledger is not None:
            self.ledger["tracked"] -= self.memory


def add_instance(name, memory, last_used, ledger, live_connected=None):
    """File instance when live_connected is None, else a live one."""
    inst = tracy_mcp.TracyInstance(name, FakeWorker(memory, live_connected, ledger))
    inst.last_used = last_used
    inst.memory_mb = memory
    if live_connected is None:
        inst.path = f"{name}.tracy"
    ledger["tracked"] += memory
    tracy_mcp.instances[name] = inst
    return inst


def setup(monkeypatch, budget, available=None, reserve=0):
    ledger = {"tracked": 0}
    tracy_mcp.instances.clear()
    monkeypatch.setattr(tracy_mcp, "_MEMORY_BUDGET_MB", budget)
    monkeypatch.setattr(tracy_mcp, "_RAM_RESERVE_MB", reserve)
    monkeypatch.setattr(tracy_mcp, "_tracked_mb", lambda: ledger["tracked"])
    monkeypatch.setattr(tracy_mcp, "_available_mb", lambda: available)
    return ledger


def test_shortfall_none_when_it_fits():
    assert tracy_mcp._budget_shortfall(100, 50, 200, 1000, 100) is None


def test_shortfall_over_budget():
    assert "memory budget" in tracy_mcp._budget_shortfall(150, 100, 200, None, 0)


def test_shortfall_over_free_ram():
    assert "free" in tracy_mcp._budget_shortfall(0, 900, None, 1000, 200)


def test_no_limits_never_short():
    assert tracy_mcp._budget_shortfall(10**6, 10**6, None, None, 0) is None


def test_estimate_scales_file_size(monkeypatch):
    monkeypatch.setattr(tracy_mcp, "_LOAD_EXPANSION", 15.0)
    assert tracy_mcp._estimate_load_mb(100 * MB) == 1500


def test_make_room_evicts_least_recently_used_first(monkeypatch):
    ledger = setup(monkeypatch, budget=1000)
    add_instance("old", 400, 1, ledger)
    add_instance("new", 400, 2, ledger)
    evicted, why = tracy_mcp._make_room(400)
    assert why is None
    assert evicted == ["old"]
    assert list(tracy_mcp.instances) == ["new"]


def test_make_room_never_evicts_connected_live(monkeypatch):
    ledger = setup(monkeypatch, budget=1000)
    add_instance("live", 700, 1, ledger, live_connected=True)
    add_instance("file", 200, 2, ledger)
    evicted, why = tracy_mcp._make_room(400)
    assert evicted == ["file"]
    assert why is not None
    assert "live" in tracy_mcp.instances


def test_make_room_evicts_disconnected_live(monkeypatch):
    ledger = setup(monkeypatch, budget=1000)
    add_instance("dead", 700, 1, ledger, live_connected=False)
    evicted, why = tracy_mcp._make_room(500)
    assert why is None
    assert evicted == ["dead"]


def test_make_room_reports_shortfall_when_nothing_evictable(monkeypatch):
    setup(monkeypatch, budget=100)
    evicted, why = tracy_mcp._make_room(500)
    assert evicted == []
    assert "memory budget" in why


def test_make_room_respects_free_ram(monkeypatch):
    ledger = setup(monkeypatch, budget=None, available=1000, reserve=200)
    add_instance("a", 100, 1, ledger)
    evicted, why = tracy_mcp._make_room(900)
    assert why is not None
    assert evicted == ["a"]


def test_make_room_refuses_oversized_request_without_evicting(monkeypatch):
    ledger = setup(monkeypatch, budget=1000)
    add_instance("keep", 300, 1, ledger)
    evicted, why = tracy_mcp._make_room(1500)
    assert evicted == []
    assert why is not None
    assert list(tracy_mcp.instances) == ["keep"]
