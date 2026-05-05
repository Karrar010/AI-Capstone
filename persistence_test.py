"""
Lab 5: Persistence Test
Proves the agent can retrieve state from a previous session using the same thread_id.
Run phase 1, then phase 2 (separate process) to verify SqliteSaver persistence.
"""
import sys
from pathlib import Path

# Ensure project root
sys.path.insert(0, str(Path(__file__).parent))

TEST_THREAD_ID = "persistence-test-123"
TEST_TOPIC = "Brief overview of Python"


def phase1():
    """Run graph until interrupt. State is checkpointed to SQLite."""
    from bwa_backend import app
    inputs = {
        "topic": TEST_TOPIC,
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "rag_chunks": [],
        "plan": None,
        "sections": [],
        "merged_md": "",
        "final": "",
        "guardrail_safe": True,
        "guardrail_reason": "",
        "security_refusal": "",
        "tool_trace": [],
    }
    config = {"configurable": {"thread_id": TEST_THREAD_ID}}
    print("Phase 1: Running graph (will stop at HITL interrupt)...")
    for step in app.stream(inputs, config=config, stream_mode="updates"):
        pass
    state = app.get_state(config)
    print(f"Phase 1 done. State saved. Next node: {state.next if state else 'N/A'}")
    print("(Stop this process. Then run: python persistence_test.py 2)")


def phase2():
    """Restart: load state from same thread_id without re-running from scratch."""
    from bwa_backend import app
    config = {"configurable": {"thread_id": TEST_THREAD_ID}}
    print("Phase 2: Loading state from previous session (same thread_id)...")
    state = app.get_state(config)
    if state and state.values:
        vals = state.values
        has_plan = bool(vals.get("plan"))
        has_merged = bool(vals.get("merged_md"))
        print(f"  plan present: {has_plan}")
        print(f"  merged_md present: {has_merged}")
        if has_plan or has_merged:
            print("PASS: Agent remembered previous context. Persistence works.")
        else:
            print("FAIL: State empty or incomplete.")
    else:
        print("FAIL: No state found. Run phase 1 first.")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "1"
    if phase == "1":
        phase1()
    elif phase == "2":
        phase2()
    else:
        print("Usage: python persistence_test.py [1|2]")
        print("  1 = Run graph, checkpoint state, exit")
        print("  2 = Load state from same thread_id (simulates restart)")
