import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch


if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")

    class AsyncOpenAI:  # pragma: no cover - simple import stub
        pass

    openai_stub.AsyncOpenAI = AsyncOpenAI
    sys.modules["openai"] = openai_stub


if "agent_framework" not in sys.modules:
    agent_framework_stub = types.ModuleType("agent_framework")

    class Executor:
        def __init__(self, id: str) -> None:
            self.id = id

    class MCPStdioTool:
        pass

    class WorkflowContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    def handler(fn):
        return fn

    def response_handler(fn):
        return fn

    agent_framework_stub.Executor = Executor
    agent_framework_stub.MCPStdioTool = MCPStdioTool
    agent_framework_stub.WorkflowContext = WorkflowContext
    agent_framework_stub.handler = handler
    agent_framework_stub.response_handler = response_handler
    sys.modules["agent_framework"] = agent_framework_stub


if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        pass

    pydantic_stub.BaseModel = BaseModel
    sys.modules["pydantic"] = pydantic_stub


from agents.intent import _load_skill_reference, answer_question
from agents.manual_edit_executor import ManualEditExecutor
from agents.schemas import ManualEditAck


class _DummyCtx:
    def __init__(self, states: dict) -> None:
        self.states = dict(states)
        self.messages = []

    def get_state(self, key: str):
        return self.states.get(key)

    def set_state(self, key: str, value) -> None:
        self.states[key] = value

    async def send_message(self, message) -> None:
        self.messages.append(message)


class IntentAndManualEditTests(unittest.IsolatedAsyncioTestCase):
    def test_load_skill_reference_defaults_to_xml(self) -> None:
        with TemporaryDirectory() as tmpdir:
            xml_skill = Path(tmpdir) / "xml.md"
            xml_skill.write_text("xml reference", encoding="utf-8")
            post_skill = Path(tmpdir) / "post.md"
            post_skill.write_text("post reference", encoding="utf-8")

            with patch("agents.intent._SKILL_FILES", {"xml": xml_skill, "postprocess": post_skill}):
                skill_type, skill_text = _load_skill_reference("unknown")

            self.assertEqual(skill_type, "xml")
            self.assertEqual(skill_text, "xml reference")

    async def test_answer_question_uses_selected_skill_reference(self) -> None:
        captured = {}

        async def fake_create(**kwargs):
            captured["messages"] = kwargs["messages"]
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="answer"))]
            )

        fake_client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=fake_create)
            )
        )

        with TemporaryDirectory() as tmpdir:
            xml_skill = Path(tmpdir) / "xml.md"
            xml_skill.write_text("xml reference", encoding="utf-8")
            post_skill = Path(tmpdir) / "post.md"
            post_skill.write_text("postprocess reference", encoding="utf-8")

            with patch("agents.intent._SKILL_FILES", {"xml": xml_skill, "postprocess": post_skill}), \
                    patch("agents.intent.AsyncOpenAI", return_value=fake_client):
                answer = await answer_question(
                    "What does this result mean?",
                    "plan context",
                    skill_type="postprocess",
                )

        self.assertEqual(answer, "answer")
        self.assertIn("postprocess reference", captured["messages"][0]["content"])
        self.assertIn("Post-Processing Guide", captured["messages"][0]["content"])

    async def test_manual_edit_refreshes_plan_state_after_rebuild(self) -> None:
        case_xml = """<?xml version="1.0" encoding="UTF-8"?>
<case>
  <casedef>
    <constantsdef>
      <gravity x="0" y="0" z="-8.5" />
      <rhop0 value="1500" />
      <coefh value="0.95" />
      <cflnumber value="0.2" />
    </constantsdef>
    <geometry>
      <definition dp="0.02">
        <pointmin x="0" y="0" z="0" />
        <pointmax x="2" y="1" z="1" />
      </definition>
      <commands>
        <mainlist>
          <drawbox />
        </mainlist>
      </commands>
    </geometry>
  </casedef>
  <execution>
    <special>
      <nnphases>
        <phase mkfluid="0">
          <rhop value="1500" />
          <visco value="0.25" />
          <tau_yield value="3.5" />
          <HBP_m value="9" />
          <HBP_n value="0.8" />
        </phase>
      </nnphases>
    </special>
    <parameters>
      <parameter key="Visco" value="0.15" />
      <parameter key="DensityDT" value="4" />
      <parameter key="DensityDTvalue" value="0.05" />
      <parameter key="TimeMax" value="7.5" />
      <parameter key="TimeOut" value="0.25" />
    </parameters>
  </execution>
</case>
"""
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "Case_Def.xml").write_text(case_xml, encoding="utf-8")

            ctx = _DummyCtx({
                "run_dir": str(run_dir),
                "plan": {
                    "geometry_xml": "<geometry />",
                    "params": {"rhop0": 1000},
                    "probe_points": [[1.0, 2.0, 3.0]],
                    "reasoning": "keep this",
                },
            })

            executor = ManualEditExecutor(mcp=object())
            with patch("agents.manual_edit_executor.rebuild_gencase_viz", new=AsyncMock()):
                await executor.on_done(
                    ManualEditAck(file_path=str(run_dir / "Case_Def.xml"), message="done"),
                    "done",
                    ctx,
                )

        self.assertEqual(ctx.states["plan"]["reasoning"], "keep this")
        self.assertEqual(ctx.states["plan"]["probe_points"], [[1.0, 2.0, 3.0]])
        self.assertIn('<definition dp="0.02">', ctx.states["plan"]["geometry_xml"])
        self.assertEqual(ctx.states["plan"]["params"]["gravity_z"], -8.5)
        self.assertEqual(ctx.states["plan"]["params"]["rhop0"], 1500.0)
        self.assertEqual(ctx.states["plan"]["params"]["DensityDT"], 4)
        self.assertTrue(ctx.messages[0].success)


if __name__ == "__main__":
    unittest.main()
