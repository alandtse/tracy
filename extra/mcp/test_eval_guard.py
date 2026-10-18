"""Run with PYTHONPATH containing the built TracyServerBindings:
    python -m pytest extra/mcp/test_eval_guard.py
"""
import asyncio
import time

import pytest

import tracy_mcp


class Worker:
    def is_connected(self):
        return False

    def shutdown(self):
        pass


@pytest.fixture(autouse=True)
def clean_instances():
    tracy_mcp.instances.clear()
    tracy_mcp.tasks.clear()
    yield
    tracy_mcp.instances.clear()
    tracy_mcp.tasks.clear()


def add(name="a"):
    inst = tracy_mcp.TracyInstance(name, Worker())
    inst.path = f"{name}.tracy"
    tracy_mcp.instances[name] = inst
    return inst


def test_busy_instance_is_not_evictable():
    inst = add()
    assert inst.is_evictable()
    inst.begin_eval()
    assert not inst.is_evictable()
    assert tracy_mcp._drop_lru() is None
    inst.end_eval()
    assert tracy_mcp._drop_lru() == "a"


def test_unload_refused_while_async_eval_runs():
    async def scenario():
        add()
        started = await tracy_mcp.tracy_eval("import time; time.sleep(0.5); print('done')", "a", async_mode=True)
        refused = await tracy_mcp.unload_capture("a")
        assert "still running" in refused
        assert "a" in tracy_mcp.instances
        task_id = started["task_id"]
        deadline = time.time() + 5
        while tracy_mcp.tasks[task_id].status in ("pending", "running") and time.time() < deadline:
            await asyncio.sleep(0.05)
        assert tracy_mcp.tasks[task_id].status == "completed"
        # end_eval runs after the status flips, so allow it a moment
        for _ in range(100):
            if tracy_mcp.instances["a"].active_evals == 0:
                break
            await asyncio.sleep(0.02)
        assert "unloaded" in await tracy_mcp.unload_capture("a")
        assert "a" not in tracy_mcp.instances

    asyncio.run(scenario())


def test_failed_eval_releases_the_instance():
    async def scenario():
        inst = add()
        out = await tracy_mcp.tracy_eval("1/0", "a", async_mode=True)
        task_id = out["task_id"]
        for _ in range(200):
            if tracy_mcp.tasks[task_id].status == "failed" and inst.active_evals == 0:
                break
            await asyncio.sleep(0.02)
        assert inst.active_evals == 0
        assert "unloaded" in await tracy_mcp.unload_capture("a")

    asyncio.run(scenario())


def test_unload_unknown_instance():
    assert "not found" in asyncio.run(tracy_mcp.unload_capture("nope"))
