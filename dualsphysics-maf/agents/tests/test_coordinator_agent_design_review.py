import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _import_coordinator_module():
    fake_framework = types.ModuleType("agent_framework")
    for name in ("AgentExecutorRequest", "AgentExecutorResponse", "Executor", "MCPStdioTool", "Message"):
        setattr(fake_framework, name, type(name, (), {}))
    fake_framework.WorkflowContext = type(
        "WorkflowContext", (), {"__class_getitem__": classmethod(lambda cls, _item: cls)}
    )
    fake_framework.handler = lambda fn: fn
    fake_framework.response_handler = lambda fn: fn
    sys.modules.setdefault("agent_framework", fake_framework)

    fake_visualize = types.ModuleType("agents.tools.visualize_geometry")
    fake_visualize.visualize_geometry = lambda *_args, **_kwargs: "ok"
    sys.modules.setdefault("agents.tools.visualize_geometry", fake_visualize)

    fake_schemas = types.ModuleType("agents.schemas")
    for name in ("PhysicsParams", "ReviewRequest", "SimulationPlan"):
        setattr(fake_schemas, name, type(name, (), {}))
    sys.modules.setdefault("agents.schemas", fake_schemas)

    path = Path(__file__).resolve().parents[1] / "coordinator.py"
    spec = importlib.util.spec_from_file_location("agents.coordinator_test_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CoordinatorAgentDesignReviewTests(unittest.TestCase):
    def test_detects_agent_design_review_request(self):
        module = _import_coordinator_module()
        is_request = module._is_agent_design_review_request
        self.assertTrue(
            is_request("Can you review my current agent design and give me solid suggestions?")
        )

    def test_ignores_simulation_scenario_with_review_words(self):
        module = _import_coordinator_module()
        is_request = module._is_agent_design_review_request
        self.assertFalse(
            is_request("Review the simulation geometry and suggest probe updates for this run.")
        )

    def test_review_payload_has_actionable_suggestions(self):
        module = _import_coordinator_module()
        build_review = module._build_agent_design_review
        payload = build_review()
        self.assertEqual(payload["request_type"], "agent_design_review")
        self.assertIsInstance(payload["suggestions"], list)
        self.assertTrue(payload["suggestions"])


if __name__ == "__main__":
    unittest.main()
