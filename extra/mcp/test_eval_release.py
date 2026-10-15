"""Run with PYTHONPATH containing the built TracyServerBindings:
    python -m pytest extra/mcp/test_eval_release.py
"""
import asyncio
import gc
import time
import weakref

import pytest

import tracy_mcp


class Worker:
    def shutdown(self):
        pass


@pytest.fixture(autouse=True)
def no_cyclic_gc():
    tracy_mcp.instances.clear()
    gc.collect()
    gc.disable()
    yield
    gc.enable()
    tracy_mcp.instances.clear()


def eval_then_unload(code):
    """Run `code` on instance a (instance b is also loaded), unload both, and
    return weak references to the two workers."""
    worker, other = Worker(), Worker()
    refs = (weakref.ref(worker), weakref.ref(other))
    for name, w in (("a", worker), ("b", other)):
        tracy_mcp.instances[name] = tracy_mcp.TracyInstance(name, w)
    try:
        tracy_mcp._execute_eval_sync(code, worker)
    except ZeroDivisionError:
        pass
    del worker, other, w

    async def unload():
        await tracy_mcp.unload_capture("a")
        await tracy_mcp.unload_capture("b")

    asyncio.run(unload())
    return refs


def test_unload_frees_workers_after_eval_defines_a_function():
    refs = eval_then_unload("def f():\n    return ctx\nprint(f() is ctx)")
    assert all(r() is None for r in refs)


def test_unload_frees_workers_after_eval_defines_a_lambda():
    refs = eval_then_unload("g = lambda: ctx")
    assert all(r() is None for r in refs)


def test_unload_frees_workers_after_a_failing_eval():
    refs = eval_then_unload("def f():\n    return 1\n1/0")
    assert all(r() is None for r in refs)


def test_expression_result_still_returned():
    assert tracy_mcp._execute_eval_sync("1 + 1", Worker()) == "2"


def test_thread_started_by_eval_keeps_its_globals():
    scratch = {}
    code = (
        "import threading, time\n"
        "HELPER = 5\n"
        "def run():\n"
        "    time.sleep(0.2)\n"
        "    scratch['v'] = HELPER + len(str(ctx is not None))\n"
        "threading.Thread(target=run).start()\n"
    )
    tracy_mcp._execute_eval_sync(code, Worker(), scratch)
    deadline = time.time() + 5
    while "v" not in scratch and time.time() < deadline:
        time.sleep(0.05)
    assert scratch.get("v") == 9
