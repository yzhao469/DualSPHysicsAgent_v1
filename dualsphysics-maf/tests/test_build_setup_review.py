import importlib.util
import json
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_PATH = REPO_ROOT / "agents/executors/build.py"
SETUP_REVIEW_PATH = REPO_ROOT / "agents/executors/setup_review.py"
GENCASE_XML_ERROR = "GenCase stderr: malformed XML"


def _install_module_stubs(modules: dict[str, types.ModuleType]) -> callable:
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)

    def cleanup() -> None:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    return cleanup


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeWorkflowContext:
    def __init__(self, initial_state=None):
        self.state = dict(initial_state or {})
        self.messages = []
        self.requests = []

    def get_state(self, key):
        return self.state.get(key)

    def set_state(self, key, value):
        self.state[key] = value

    async def send_message(self, message):
        self.messages.append(message)

    async def request_info(self, request_data, response_type):
        self.requests.append((request_data, response_type))


def _make_agent_framework_stub():
    module = types.ModuleType("agent_framework")

    class Executor:
        def __init__(self, id):
            self.id = id

    class MCPStdioTool:
        pass

    class WorkflowContext:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

    class AgentExecutorResponse:
        pass

    def handler(fn):
        return fn

    def response_handler(fn):
        return fn

    module.Executor = Executor
    module.MCPStdioTool = MCPStdioTool
    module.WorkflowContext = WorkflowContext
    module.AgentExecutorResponse = AgentExecutorResponse
    module.handler = handler
    module.response_handler = response_handler
    return module


def _make_schema_stub():
    module = types.ModuleType("agents.schemas")

    @dataclass
    class BuildResult:
        run_dir: str
        success: bool
        message: str

    @dataclass
    class ReviewResult:
        route: str
        feedback: str

    @dataclass
    class SetupReviewRequest:
        summary: str

    class PhysicsParams:
        def __init__(self, **values):
            self.values = values

        def model_dump(self):
            return dict(self.values)

    class SimulationPlan:
        def __init__(self, data):
            self.geometry_xml = data.get("geometry_xml")
            self.params = PhysicsParams(**data.get("params", {}))
            self.probe_points = data.get("probe_points", [])
            self.reasoning = data.get("reasoning", "")
            self._data = data

        @classmethod
        def model_validate_json(cls, raw_text):
            return cls(json.loads(raw_text))

        @classmethod
        def model_validate(cls, data):
            return cls(data)

        def model_dump(self):
            return dict(self._data)

    module.BuildResult = BuildResult
    module.ReviewResult = ReviewResult
    module.SetupReviewRequest = SetupReviewRequest
    module.PhysicsParams = PhysicsParams
    module.SimulationPlan = SimulationPlan
    return module


def _make_common_agent_packages():
    agents_pkg = types.ModuleType("agents")
    agents_pkg.__path__ = []
    utils_pkg = types.ModuleType("agents.utils")
    utils_pkg.__path__ = []
    tools_pkg = types.ModuleType("agents.tools")
    tools_pkg.__path__ = []
    return agents_pkg, utils_pkg, tools_pkg


class BuildExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        agents_pkg, utils_pkg, tools_pkg = _make_common_agent_packages()
        schemas_mod = _make_schema_stub()
        viz_mod = types.ModuleType("agents.tools.visualize_geometry")
        viz_mod.visualize_geometry = lambda path: f"viz:{path}"

        cleanup = _install_module_stubs({
            "agent_framework": _make_agent_framework_stub(),
            "agents": agents_pkg,
            "agents.schemas": schemas_mod,
            "agents.tools": tools_pkg,
            "agents.tools.visualize_geometry": viz_mod,
            "agents.utils": utils_pkg,
        })
        self.addCleanup(cleanup)
        self.build_module = _load_module("build_under_test", BUILD_PATH)

    async def test_failed_build_keeps_run_dir_for_recovery(self):
        plan = {
            "geometry_xml": "<geometry/>",
            "params": {"rhop0": 1000},
            "probe_points": [],
            "reasoning": "test",
        }
        result = types.SimpleNamespace(
            agent_response=types.SimpleNamespace(text=json.dumps(plan))
        )
        ctx = FakeWorkflowContext()
        executor = self.build_module.BuildExecutor(mcp=None, base_dir="/tmp/project")
        executor._new_run_dir = lambda: "/tmp/project/runs/run_test"

        async def fail_build(plan_data, base_xml, run_dir):
            raise RuntimeError("bad xml")

        executor._build = fail_build

        await executor.on_plan(result, ctx)

        self.assertEqual(ctx.get_state("run_dir"), "/tmp/project/runs/run_test")
        self.assertEqual(len(ctx.messages), 1)
        self.assertFalse(ctx.messages[0].success)
        self.assertEqual(ctx.messages[0].run_dir, "/tmp/project/runs/run_test")
        self.assertIn("bad xml", ctx.messages[0].message)


class SetupReviewExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        agents_pkg, utils_pkg, tools_pkg = _make_common_agent_packages()
        schemas_mod = _make_schema_stub()

        build_utils_mod = types.ModuleType("agents.utils.build_utils")
        async def fake_rebuild_gencase_viz(mcp, run_dir):
            return None
        build_utils_mod.rebuild_gencase_viz = fake_rebuild_gencase_viz

        intent_mod = types.ModuleType("agents.utils.intent")
        async def answer_question(question, plan_context):
            return "answer"
        intent_mod.answer_question = answer_question

        patch_utils_mod = types.ModuleType("agents.utils.patch_utils")
        async def generate_patch(current_xml, plan_data, changes):
            return {}
        def merge_patch(plan_data, patch):
            plan_data.update(patch)
        patch_utils_mod.generate_patch = generate_patch
        patch_utils_mod.merge_patch = merge_patch

        skill_loader_mod = types.ModuleType("agents.utils.skill_loader")
        skill_loader_mod.get_skill_content = lambda: "skill"

        openai_mod = types.ModuleType("openai")
        class PlaceholderAsyncOpenAI:
            def __init__(self):
                self.chat = None
        openai_mod.AsyncOpenAI = PlaceholderAsyncOpenAI

        cleanup = _install_module_stubs({
            "agent_framework": _make_agent_framework_stub(),
            "agents": agents_pkg,
            "agents.schemas": schemas_mod,
            "agents.tools": tools_pkg,
            "agents.utils": utils_pkg,
            "agents.utils.build_utils": build_utils_mod,
            "agents.utils.intent": intent_mod,
            "agents.utils.patch_utils": patch_utils_mod,
            "agents.utils.skill_loader": skill_loader_mod,
            "openai": openai_mod,
        })
        self.addCleanup(cleanup)
        self.setup_review_module = _load_module("setup_review_under_test", SETUP_REVIEW_PATH)
        self.schemas = schemas_mod

    async def test_build_failure_enters_review_loop_with_error_context(self):
        ctx = FakeWorkflowContext({
            "plan": {
                "geometry_xml": "<geometry/>",
                "params": {"rhop0": 1000},
                "probe_points": [[0, 0, 0]],
                "reasoning": "test plan",
            },
            "run_dir": "/tmp/run_dir",
        })
        executor = self.setup_review_module.SetupReviewExecutor(mcp=None, base_dir="/tmp/project")
        result = self.schemas.BuildResult(
            run_dir="/tmp/run_dir",
            success=False,
            message=GENCASE_XML_ERROR,
        )

        await executor.on_build_complete(result, ctx)

        self.assertEqual(ctx.messages, [])
        self.assertEqual(len(ctx.requests), 1)
        request, response_type = ctx.requests[0]
        self.assertIs(response_type, str)
        self.assertIn("Build failed before the setup could be reviewed.", request.summary)
        self.assertIn(GENCASE_XML_ERROR, request.summary)
        system_prompt = ctx.get_state("setup_review_history")[0]["content"]
        self.assertIn("### Current Build Error", system_prompt)
        self.assertIn(GENCASE_XML_ERROR, system_prompt)
        self.assertEqual(ctx.get_state("setup_review_retry_count"), 0)
        self.assertEqual(
            ctx.get_state("setup_review_last_error"),
            GENCASE_XML_ERROR,
        )

    async def test_patch_success_refreshes_prompt_and_clears_error_state(self):
        class FakeToolCall:
            def __init__(self):
                self.id = "call_patch"
                self.function = types.SimpleNamespace(
                    name="patch_and_rebuild",
                    arguments=json.dumps({"changes": "Fix the XML"}),
                )

        class FakePatchMessage:
            content = None
            tool_calls = [FakeToolCall()]

            def model_dump(self, exclude_none=True):
                return {"role": "assistant", "tool_calls": ["patch_and_rebuild"]}

        class FakeTextMessage:
            content = "Recovered successfully"
            tool_calls = []

            def model_dump(self, exclude_none=True):
                return {"role": "assistant", "content": self.content}

        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            async def create(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return types.SimpleNamespace(
                        choices=[types.SimpleNamespace(message=FakePatchMessage())]
                    )
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=FakeTextMessage())]
                )

        class FakeAsyncOpenAI:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=FakeCompletions())

        self.setup_review_module.AsyncOpenAI = FakeAsyncOpenAI

        ctx = FakeWorkflowContext({
            "plan": {
                "geometry_xml": "<geometry/>",
                "params": {"rhop0": 1000},
                "probe_points": [],
                "reasoning": "test plan",
            },
            "run_dir": "/tmp/run_dir",
            "setup_review_history": [{
                "role": "system",
                "content": self.setup_review_module._build_system_prompt(
                    {
                        "geometry_xml": "<geometry/>",
                        "params": {"rhop0": 1000},
                        "probe_points": [],
                        "reasoning": "test plan",
                    },
                    "/tmp/run_dir",
                    build_error=GENCASE_XML_ERROR,
                ),
            }],
            "setup_review_retry_count": 2,
            "setup_review_last_error": GENCASE_XML_ERROR,
        })
        executor = self.setup_review_module.SetupReviewExecutor(mcp=None, base_dir="/tmp/project")

        async def succeed_patch(changes, plan_data, run_dir, ctx):
            return "Patch applied successfully. ParaView should reopen with the updated geometry."

        executor._patch_and_rebuild = succeed_patch

        await executor.on_user_reply(
            self.schemas.SetupReviewRequest(summary="summary"),
            "please fix it",
            ctx,
        )

        self.assertEqual(ctx.get_state("setup_review_retry_count"), 0)
        self.assertIsNone(ctx.get_state("setup_review_last_error"))
        system_prompt = ctx.get_state("setup_review_history")[0]["content"]
        self.assertIn("Build completed successfully.", system_prompt)
        self.assertNotIn("### Current Build Error", system_prompt)
        self.assertEqual(len(ctx.requests), 1)
        self.assertEqual(ctx.requests[0][0].summary, "Recovered successfully")

    async def test_approve_is_blocked_while_build_error_remains(self):
        class FakeApproveToolCall:
            def __init__(self):
                self.id = "call_approve"
                self.function = types.SimpleNamespace(
                    name="approve",
                    arguments=json.dumps({}),
                )

        class FakeApproveMessage:
            content = None
            tool_calls = [FakeApproveToolCall()]

            def model_dump(self, exclude_none=True):
                return {"role": "assistant", "tool_calls": ["approve"]}

        class FakeTextMessage:
            content = "Please fix the build error first."
            tool_calls = []

            def model_dump(self, exclude_none=True):
                return {"role": "assistant", "content": self.content}

        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            async def create(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return types.SimpleNamespace(
                        choices=[types.SimpleNamespace(message=FakeApproveMessage())]
                    )
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=FakeTextMessage())]
                )

        class FakeAsyncOpenAI:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=FakeCompletions())

        self.setup_review_module.AsyncOpenAI = FakeAsyncOpenAI

        ctx = FakeWorkflowContext({
            "plan": {
                "geometry_xml": "<geometry/>",
                "params": {"rhop0": 1000},
                "probe_points": [],
                "reasoning": "test plan",
            },
            "run_dir": "/tmp/run_dir",
            "setup_review_history": [{"role": "system", "content": "prompt"}],
            "setup_review_last_error": GENCASE_XML_ERROR,
        })
        executor = self.setup_review_module.SetupReviewExecutor(mcp=None, base_dir="/tmp/project")

        await executor.on_user_reply(
            self.schemas.SetupReviewRequest(summary="summary"),
            "looks good",
            ctx,
        )

        self.assertEqual(ctx.messages, [])
        self.assertEqual(len(ctx.requests), 1)
        self.assertEqual(ctx.requests[0][0].summary, "Please fix the build error first.")
        tool_messages = [
            entry for entry in ctx.get_state("setup_review_history")
            if entry.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Cannot approve yet", tool_messages[0]["content"])

    async def test_patch_retry_limit_routes_to_replan(self):
        class FakeToolCall:
            def __init__(self):
                self.id = "call_1"
                self.function = types.SimpleNamespace(
                    name="patch_and_rebuild",
                    arguments=json.dumps({"changes": "Fix the XML"}),
                )

        class FakeMessage:
            content = None
            tool_calls = [FakeToolCall()]

            def model_dump(self, exclude_none=True):
                return {"role": "assistant", "tool_calls": ["patch_and_rebuild"]}

        class FakeCompletions:
            async def create(self, **kwargs):
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=FakeMessage())]
                )

        class FakeAsyncOpenAI:
            def __init__(self):
                self.chat = types.SimpleNamespace(completions=FakeCompletions())

        self.setup_review_module.AsyncOpenAI = FakeAsyncOpenAI

        ctx = FakeWorkflowContext({
            "plan": {
                "geometry_xml": "<geometry/>",
                "params": {"rhop0": 1000},
                "probe_points": [],
                "reasoning": "test plan",
            },
            "run_dir": "/tmp/run_dir",
            "setup_review_history": [{"role": "system", "content": "prompt"}],
            "setup_review_retry_count": self.setup_review_module.MAX_BUILD_RECOVERY_ATTEMPTS - 1,
        })
        executor = self.setup_review_module.SetupReviewExecutor(mcp=None, base_dir="/tmp/project")

        async def fail_patch(changes, plan_data, run_dir, ctx):
            raise RuntimeError(GENCASE_XML_ERROR)

        executor._patch_and_rebuild = fail_patch

        await executor.on_user_reply(
            self.schemas.SetupReviewRequest(summary="summary"),
            "please fix it",
            ctx,
        )

        self.assertEqual(len(ctx.messages), 1)
        self.assertEqual(ctx.messages[0].route, "full_replan")
        self.assertIn(GENCASE_XML_ERROR, ctx.messages[0].feedback)
        self.assertEqual(
            ctx.get_state("setup_review_retry_count"),
            self.setup_review_module.MAX_BUILD_RECOVERY_ATTEMPTS,
        )

    async def test_patch_rebuild_uses_base_xml_when_case_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            case_dir = base_dir / "cases"
            case_dir.mkdir()
            base_xml = case_dir / "BaseCase_Def.xml"
            base_xml.write_text("<base-case />")
            run_dir = base_dir / "runs" / "run_missing"
            run_dir.mkdir(parents=True)

            captured = {}

            async def fake_generate_patch(current_xml, plan_data, changes):
                captured["current_xml"] = current_xml
                return {}

            async def fake_rebuild_gencase_viz(mcp, current_run_dir):
                captured["run_dir"] = current_run_dir

            self.setup_review_module.generate_patch = fake_generate_patch
            self.setup_review_module.rebuild_gencase_viz = fake_rebuild_gencase_viz
            self.setup_review_module.merge_patch = lambda plan_data, patch: None

            ctx = FakeWorkflowContext({"base_xml": str(base_xml)})
            executor = self.setup_review_module.SetupReviewExecutor(mcp=None, base_dir=str(base_dir))

            result = await executor._patch_and_rebuild(
                "fix geometry",
                {
                    "geometry_xml": "<geometry/>",
                    "params": {"rhop0": 1000},
                    "probe_points": [],
                    "reasoning": "test",
                },
                str(run_dir),
                ctx,
            )

            self.assertEqual(captured["current_xml"], "<base-case />")
            self.assertEqual(captured["run_dir"], str(run_dir))
            self.assertIn("Patch applied successfully", result)


if __name__ == "__main__":
    unittest.main()
