# DualSPHysics MAF — Project Notes for Claude

## 项目位置
```
/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf/
```
Python venv: `.venv/`
Run with: `.venv/bin/python`

---

## 架构（2026-03-03 — 7-Executor Flexible Workflow）

**核心模式**：LLM 只做推理（返回结构化 SimulationPlan JSON），
Python 代码确定性地编排所有 MCP 工具调用。

### Workflow Diagram

ReviewExecutor is a single node in the workflow graph, but handles two internal
phases (`plan` and `viz`). Both phases offer the same 5-way intent routing.
The only difference: "approve" in plan phase → Build; "approve" in viz phase → Sim.

```
                         ┌──────────────────────────────────────────────┐
                         │                                              │
                         ▼                                              │
                  ┌──────────────┐                                      │
                  │  Planning    │                                      │
                  │  Executor    │                                      │
                  └──────┬───────┘                                      │
                         │                                              │
                         ▼                                              │
                  ┌──────────────┐                                      │
                  │    Agent     │  (GPT-4o → SimulationPlan JSON)      │
                  │   Executor   │                                      │
                  └──────┬───────┘                                      │
                         │                                              │
                         ▼                                              │
                  ┌──────────────┐                                      │
                  │   Review     │  HITL gate #1: "plan" phase          │
                  │  (plan)      │  User sees plan summary              │
                  └──────┬───────┘                                      │
                         │                                              │
                   5-way switch_case                                    │
          ┌────────┬─────┼──────────┬───────────┐                       │
          ▼        ▼     ▼          ▼           ▼                       │
        Build    Patch  ManualEdit  Question   Planning ────────────────┘
        Exec     Exec    Exec      (Q&A loop)  (full replan)
          │        │       │
          │        │       │
          ▼        ▼       ▼
        ┌─────────────────────┐
        │       Review        │  HITL gate #2: "viz" phase
        │      (viz)          │  User sees ParaView visualization
        └─────────┬───────────┘
                  │
            5-way switch_case
          ┌───────┼──────────┬───────────┬──────────────┐
          ▼       ▼          ▼           ▼              ▼
        Sim     Patch    ManualEdit   Question       Planning
        Exec    Exec      Exec       (Q&A loop)    (full replan)
       (done)     │          │
                  │          │
                  └──────────┘
                  back to Review (viz)
```

### 5-Way Intent Routes (available at BOTH HITL gates)

| Intent | Condition | Action |
|--------|-----------|--------|
| **approve** | `ReviewResult.route == "build"` (plan) or `"sim"` (viz) | Proceed to next stage |
| **agent_patch** | `PatchRequest` | LLM-driven targeted XML patch → rebuild → back to Review |
| **manual_edit** | `ManualEditRequest` | User manually edits XML → rebuild → back to Review |
| **question** | Q&A loop | GPT-4o-mini answers, then re-prompts same gate |
| **full_replan** | `Default` → PlanningExecutor | Agent re-generates plan from scratch |

### 7 Executors

1. `PlanningExecutor` (id="planning") — wraps scenario/revision → AgentExecutorRequest; detects datalake files
2. `AgentExecutor` (MAF built-in) — GPT-4o + `response_format=SimulationPlan`
3. `ReviewExecutor` (id="review") — dual-phase HITL gate + 5-way intent classification
4. `BuildExecutor` (id="build") — set_geometry → modify_xml → generate_points → run_gencase → visualize
5. `SimExecutor` (id="sim") — run_simulation → run_measuretool → compute_metrics → yield_output (terminal)
6. `PatchExecutor` (id="patch") — LLM-driven targeted patching of current case XML
7. `ManualEditExecutor` (id="manual_edit") — HITL manual XML editing + rebuild

### HITL Mechanism

1. ReviewExecutor 调用 `ctx.request_info(ReviewRequest(...))`
2. Workflow 暂停，main.py 事件循环提示用户 `input()`
3. `workflow.run(responses={request_id: user_reply})` 恢复
4. 用户提问时，`answer_question()` 用 GPT-4o-mini 回答（上下文：plan + skill file），然后 re-prompt

---

## 项目文件清单

### MCP Server（7 个工具，无变化）
| 文件 | 状态 | 说明 |
|------|------|------|
| `mcp_server/config.py` | ✅ | 路径配置 |
| `mcp_server/__init__.py` | ✅ | |
| `mcp_server/tools/__init__.py` | ✅ | |
| `mcp_server/tools/_subprocess.py` | ✅ | 共享异步子进程 helper |
| `mcp_server/tools/_xml_utils.py` | ✅ | 共享 XML 预处理（`preprocess_xml`） |
| `mcp_server/tools/xml_modifier.py` | ✅ | 物理/执行参数修改（constantsdef + nnphases + execution） |
| `mcp_server/tools/set_geometry.py` | ✅ | 几何替换工具：验证并拼接 `<geometry>` XML 到 case 文件 |
| `mcp_server/tools/generate_points.py` | ✅ | 从 probe_points 或 probe_xs × probe_zs 生成 POINTSLIST 文件 |
| `mcp_server/tools/run_gencase.py` | ✅ | |
| `mcp_server/tools/run_simulation.py` | ✅ | |
| `mcp_server/tools/run_measuretool.py` | ✅ | |
| `mcp_server/tools/metrics.py` | ✅ | |
| `mcp_server/server.py` | ✅ | FastMCP，7 个工具 |

### Workflow + Agent（7-Executor 架构）
| 文件 | 状态 | 说明 |
|------|------|------|
| `agents/__init__.py` | ✅ | |
| `agents/schemas.py` | ✅ | Pydantic 模型：SimulationPlan, PhysicsParams, ReviewRequest, ReviewResult, BuildResult, PatchRequest, ManualEditRequest, ManualEditAck |
| `agents/simulation_agent.py` | ✅ | SimulationPlanner (Agent)：OpenAI GPT-4o + 结构化输出 |
| `agents/workflow.py` | ✅ | WorkflowBuilder 配置：7 executor 注册 + 5-way switch_case 路由 |
| `agents/executors/__init__.py` | ✅ | Re-exports all 6 executor classes |
| `agents/executors/planning.py` | ✅ | PlanningExecutor：包装场景/修改意见 → AgentExecutorRequest; LLM-based datalake detection |
| `agents/executors/review.py` | ✅ | ReviewExecutor：双阶段 HITL 审核门（plan + viz）+ 5-way 路由 |
| `agents/executors/build.py` | ✅ | BuildExecutor：set_geometry → modify_xml → generate_points → run_gencase → visualize |
| `agents/executors/sim.py` | ✅ | SimExecutor：run_simulation → run_measuretool → compute_metrics → yield_output |
| `agents/executors/patch.py` | ✅ | PatchExecutor：LLM-driven targeted XML patching + rebuild |
| `agents/executors/manual_edit.py` | ✅ | ManualEditExecutor：HITL manual XML editing + rebuild |
| `agents/utils/__init__.py` | ✅ | |
| `agents/utils/build_utils.py` | ✅ | 共享 `rebuild_gencase_viz()`，PatchExecutor 和 ManualEditExecutor 复用 |
| `agents/utils/intent.py` | ✅ | 5-way intent classification + `answer_question()` Q&A + `resolve_datalake_file()` LLM file resolver |
| `agents/prompts/simulation_agent.j2` | ✅ | 简化模板：仅几何 DSL + 物理推理 + JSON schema |
| `agents/tools/__init__.py` | ✅ | |
| `agents/tools/visualize_geometry.py` | ✅ | ParaView VTK 可视化（WSL2 兼容） |

### Datalake
| 文件 | 状态 | 说明 |
|------|------|------|
| `datalake/` | ✅ | 用户提供的 XML cases；PlanningExecutor 通过 LLM 自动检测并注入为 base_xml |

### 已删除
| 文件 | 说明 |
|------|------|
| `agents/coordinator.py` | ❌ 已删除，逻辑拆分为 7 个 executor |
| `agents/tools/user_review.py` | ❌ 已删除，HITL 由 workflow request_info 取代 |

### 案例 & 技能文件
| 文件 | 状态 | 说明 |
|------|------|------|
| `cases/BaseCase_Def.xml` | ✅ | 通用基础 XML 模板（clean XML，几何由 set_geometry 替换） |
| `cases/CaseDebrisFlow2D_Def.xml` | ✅ | 旧版 DebrisFlow2D 模板（保留作参考） |
| `cases/CaseDebrisFlow2D_Points.txt` | ✅ | 静态探针点（保留作参考） |
| `cases/ground_truth/` | ⬜ | 目录存在（含 `.gitkeep`），CSV 未生成 |
| `skills/dualsphysics_xml_guide.md` | ✅ | 全面的 GenCase 几何 DSL 参考 + 物理参数 + 材料原型 |

### 入口 & 配置
| 文件 | 状态 | 说明 |
|------|------|------|
| `main.py` | ✅ | Workflow 事件循环 + HITL（terminal input） |
| `main_smoke.py` | ✅ | 显式数值参数烟雾测试 |
| `requirements.txt` | ✅ | 含 jinja2, openai, pydantic |
| `.gitignore` | ✅ | 排除 `.venv/`、`runs/`、`__pycache__/`、`*.log`、`.env` |
| `README.md` | ✅ | |

---

## Workflow Phases (see diagram above for full routing)

### Phase 1 — PlanningExecutor + AgentExecutor
PlanningExecutor 接收场景描述。若 datalake/ 有 XML 文件，用 GPT-4o-mini (`resolve_datalake_file()`)
判断用户是否引用了某个文件（支持模糊匹配）。匹配则注入 XML 上下文 + 设置 `base_xml` 状态。
然后发给 AgentExecutor → GPT-4o 返回 SimulationPlan JSON。

### Phase 2 — ReviewExecutor HITL gate #1（plan phase）
展示几何 XML、参数表、探针坐标。用户 5 种选择：
- **approve** → BuildExecutor
- **agent_patch** → PatchExecutor（LLM 修改 XML）
- **manual_edit** → ManualEditExecutor（用户手动编辑）
- **question** → GPT-4o-mini 回答，循环
- **full_replan** → PlanningExecutor 重新生成

### Phase 3 — BuildExecutor
确定性调用：`set_geometry` → `modify_xml` → `generate_points_file` → `run_gencase` → `visualize_geometry`（ParaView）
（PatchExecutor/ManualEditExecutor 完成后也回到 ReviewExecutor）

### Phase 4 — ReviewExecutor HITL gate #2（viz phase）
用户查看 ParaView 可视化，同样 5 种选择。approve → SimExecutor。

### Phase 5 — SimExecutor (terminal)
`run_simulation` → `run_measuretool` → `compute_metrics` → yield_output(JSON 摘要)

---

## 工具分工

| 工具 | 职责 |
|------|------|
| `set_geometry` | 替换 `<geometry>` 块（验证 + 拼接），处理 dp、drawbox 等所有绘图命令 |
| `modify_xml` | 修改物理/执行参数（constantsdef、nnphases、execution/parameters） |
| `generate_points_file` | 支持 `probe_points`（显式三元组）和 `probe_xs × probe_zs`（交叉积）两种模式 |

### modify_xml 支持的参数（15 个，不含几何）

**constantsdef**: `gravity_z`, `rhop0`, `coefh`, `cflnumber`
**nnphases** (mkfluid=0): `phase_rhop`, `visco_nn`, `tau_yield`, `HBP_m`, `HBP_n`
**execution/parameters**: `Visco`, `DensityDT`, `DensityDTvalue`, `TimeMax`, `TimeOut`

---

## Stub Chrono Libraries

DualSPHysics CPU/GPU 二进制在 `bin/linux/` 里没有附带 `libdsphchrono.so` 等。
已在 `bin/linux/` 创建三个 stub `.so`（空函数体汇编，31 个符号）。
`run_simulation.py` 通过 `LD_LIBRARY_PATH=BIN_DIR` 传递给子进程。

---

## 关键实现细节

### XML 预处理（_xml_utils.py）
`CaseDebrisFlow2D_Def.xml` 含非标准内容（三连横线注释、属性值内未转义 `<`/`>`、`%` 注释）。
`preprocess_xml()` 修复这些问题。`BaseCase_Def.xml` 是 clean XML，无需预处理但仍兼容。

### agent_framework RC1 API — Workflow 模式
```python
# Coordinator: Executor with @handler and @response_handler
# Agent: Agent(client=OpenAIChatClient(...), default_options={"response_format": SimulationPlan})
# Workflow: WorkflowBuilder(start_executor=coordinator).add_edge(...).build()
# HITL: ctx.request_info(ReviewRequest(...)) → workflow pauses → responses={id: reply}
# MCP: mcp.call_tool("tool_name", **kwargs) → str
```
- `opentelemetry-semantic-conventions-ai` 需固定 `==0.4.13`
- 需要 `OPENAI_API_KEY` 环境变量

### WSL2 可视化
`visualize_geometry.py` 检测 WSL2，用 `wslpath -w` + `cmd.exe /c start` 打开 VTK 文件。

### MeasureTool Points 文件格式
每个探针点用一个 `POINTSLIST` 块（origin / step / count）。
MeasureTool 输出 `_Vel.csv` + `_Rhop.csv`，`;` 分隔，前 3 行是元数据。

---

## 下一步

1. **生成 ground truth**：用默认参数跑完整模拟（`TimeMax=5.0`），MeasureTool 输出存为 `cases/ground_truth/PointsMeasure.csv`

2. **完善 skill file**：请领域专家扩充材料原型表

3. **推送到 GitHub**：注意 `config.py` 和 `simulation_agent.py` 里有硬编码绝对路径

4. **Agent 2 + 优化循环**：后续实现
