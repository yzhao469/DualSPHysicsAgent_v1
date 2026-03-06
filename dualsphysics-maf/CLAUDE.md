# DualSPHysics MAF — Project Notes for Claude

## 项目位置
```
/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf/
```
Python venv: `.venv/`
Run with: `.venv/bin/python`

---

## 架构（2026-03-05 — 8-Executor End-to-End Workflow）

**核心模式**：LLM 只做推理（返回结构化 JSON），
Python 代码确定性地编排所有 MCP 工具调用。

### Workflow Diagram

ReviewExecutor is a single node in the workflow graph, but handles three internal
phases (`plan`, `viz`, `results`). All phases offer 5-way intent routing.
- "approve" in plan phase → Build
- "approve" in viz phase → Sim
- "approve" in results phase → terminal (workflow done)

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
          │       │          │
          │       └──────────┘
          │       back to Review (viz)
          ▼
        ┌──────────────┐
        │   Analyze    │  Default: PartVTK + MeasureTool + ParaView
        │   Executor   │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │    Review    │  HITL gate #3: "results" phase
        │  (results)   │  User sees post-processing summary
        └──────┬───────┘
               │
         5-way routing
        ┌──────┼──────────┬───────────┐
        ▼      ▼          ▼           ▼
      Done   Analyze    Question   Planning
    (terminal) (user     (Q&A)   (full replan
               request)           with warning)
               │
               └──→ Review (results)
```

### 5-Way Intent Routes

| Intent | Plan phase | Viz phase | Results phase |
|--------|-----------|-----------|---------------|
| **approve** | → Build | → Sim | → Done (terminal) |
| **agent_patch** | → PatchExecutor | → PatchExecutor | → AnalyzeExecutor (analysis) |
| **manual_edit** | → ManualEditExecutor | → ManualEditExecutor | → AnalyzeExecutor (analysis) |
| **question** | Q&A loop | Q&A loop | Q&A loop |
| **full_replan** | → Planning | → Planning | → Planning (with cost warning) |

### 8 Executors

1. `PlanningExecutor` (id="planning") — wraps scenario/revision → AgentExecutorRequest; detects datalake files
2. `AgentExecutor` (MAF built-in) — GPT-4o + `response_format=SimulationPlan`
3. `ReviewExecutor` (id="review") — tri-phase HITL gate (plan + viz + results) + 5-way intent routing
4. `BuildExecutor` (id="build") — set_geometry → modify_xml → generate_points → run_gencase → visualize
5. `SimExecutor` (id="sim") — run_simulation (auto GPU/CPU detection) → passes to AnalyzeExecutor
6. `AnalyzeExecutor` (id="analyze") — default post-processing + LLM-driven analysis
7. `PatchExecutor` (id="patch") — LLM-driven targeted patching of current case XML
8. `ManualEditExecutor` (id="manual_edit") — HITL manual XML editing + rebuild

### HITL Mechanism

1. ReviewExecutor 调用 `ctx.request_info(ReviewRequest(...))`
2. Workflow 暂停，main.py 事件循环提示用户 `input()`
3. `workflow.run(responses={request_id: user_reply})` 恢复
4. 用户提问时，`answer_question()` 用 GPT-4o-mini 回答（上下文：plan + skill file），然后 re-prompt

---

## 项目文件清单

### MCP Server（9 个工具）
| 文件 | 状态 | 说明 |
|------|------|------|
| `mcp_server/config.py` | ✅ | 路径配置（含所有后处理二进制） |
| `mcp_server/__init__.py` | ✅ | |
| `mcp_server/tools/__init__.py` | ✅ | |
| `mcp_server/tools/_subprocess.py` | ✅ | 共享异步子进程 helper |
| `mcp_server/tools/_xml_utils.py` | ✅ | 共享 XML 预处理（`preprocess_xml`） |
| `mcp_server/tools/xml_modifier.py` | ✅ | 物理/执行参数修改 |
| `mcp_server/tools/set_geometry.py` | ✅ | 几何替换工具 |
| `mcp_server/tools/generate_points.py` | ✅ | 探针点文件生成 |
| `mcp_server/tools/run_gencase.py` | ✅ | |
| `mcp_server/tools/run_simulation.py` | ✅ | |
| `mcp_server/tools/run_measuretool.py` | ✅ | |
| `mcp_server/tools/metrics.py` | ✅ | |
| `mcp_server/tools/postprocess.py` | ✅ | 通用后处理工具包装器（PartVTK, IsoSurface, ComputeForces 等） |
| `mcp_server/tools/run_analysis.py` | ✅ | Python 分析脚本执行器（CSV 解析、绘图等） |
| `mcp_server/server.py` | ✅ | FastMCP，9 个工具 |

### Workflow + Agent（8-Executor 架构）
| 文件 | 状态 | 说明 |
|------|------|------|
| `agents/__init__.py` | ✅ | |
| `agents/schemas.py` | ✅ | SimulationPlan, PhysicsParams, ReviewRequest, ReviewResult, BuildResult, PatchRequest, ManualEditRequest, ManualEditAck, AnalysisRequest, AnalysisResult |
| `agents/simulation_agent.py` | ✅ | SimulationPlanner Agent |
| `agents/workflow.py` | ✅ | WorkflowBuilder：8 executor + switch_case 路由 |
| `agents/executors/__init__.py` | ✅ | Re-exports all 7 executor classes |
| `agents/executors/planning.py` | ✅ | PlanningExecutor |
| `agents/executors/review.py` | ✅ | ReviewExecutor：三阶段 HITL（plan + viz + results） |
| `agents/executors/build.py` | ✅ | BuildExecutor |
| `agents/executors/sim.py` | ✅ | SimExecutor：run_simulation（自动 GPU 检测）→ AnalyzeExecutor |
| `agents/executors/analyze.py` | ✅ | AnalyzeExecutor：默认后处理 + LLM 驱动分析 |
| `agents/executors/patch.py` | ✅ | PatchExecutor |
| `agents/executors/manual_edit.py` | ✅ | ManualEditExecutor |
| `agents/utils/__init__.py` | ✅ | |
| `agents/utils/build_utils.py` | ✅ | 共享 `rebuild_gencase_viz()` |
| `agents/utils/intent.py` | ✅ | 5-way intent classification + Q&A + datalake resolution |
| `agents/utils/skill_loader.py` | ✅ | 共享 skill loader（xml + postprocess 两套技能文件） |
| `agents/prompts/simulation_agent.j2` | ✅ | Jinja 模板 |
| `agents/tools/__init__.py` | ✅ | |
| `agents/tools/visualize_geometry.py` | ✅ | ParaView VTK 可视化（WSL2 兼容） |

### 技能文件
| 文件 | 状态 | 说明 |
|------|------|------|
| `skills/dualsphysics-xml/SKILL.md` | ✅ | 核心 skill：XML 结构、物理参数、材料原型、探针放置 |
| `skills/dualsphysics-xml/drawing-primitives.md` | ✅ | resource：GenCase 绘图命令 |
| `skills/dualsphysics-xml/transforms-and-advanced.md` | ✅ | resource：变换栈、变量、绘图模式 |
| `skills/dualsphysics-xml/composition-patterns.md` | ✅ | resource：9 个完整几何示例 |
| `skills/dualsphysics-postprocess/SKILL.md` | ✅ | 后处理 skill：工具概览、常用模式、分析指南 |
| `skills/dualsphysics-postprocess/partvtk-help.md` | ✅ | resource：PartVTK CLI 参考 |
| `skills/dualsphysics-postprocess/isosurface-help.md` | ✅ | resource：IsoSurface CLI 参考 |
| `skills/dualsphysics-postprocess/other-tools-help.md` | ✅ | resource：ComputeForces, FlowTool, BoundaryVTK, FloatingInfo, PartVTKOut, MeasureTool |

### 其他
| 文件 | 状态 | 说明 |
|------|------|------|
| `cases/BaseCase_Def.xml` | ✅ | 通用基础 XML 模板 |
| `cases/ground_truth/` | ⬜ | CSV 未生成 |
| `datalake/` | ✅ | 用户提供的 XML cases |
| `main.py` | ✅ | Workflow 事件循环 + HITL |
| `main_smoke.py` | ✅ | 烟雾测试 |

---

## Workflow Phases

### Phase 1 — Planning + Agent
PlanningExecutor 接收场景描述，检测 datalake 文件，发给 AgentExecutor 生成 SimulationPlan。

### Phase 2 — Review(plan) → Build
用户审核计划，5 种选择。approve → BuildExecutor 确定性构建。

### Phase 3 — Review(viz) → Sim
用户审核 ParaView 可视化，5 种选择。approve → SimExecutor 运行求解器。

### Phase 4 — Sim → Analyze (default)
SimExecutor 运行求解器（自动检测 GPU），然后 AnalyzeExecutor 自动执行：
- PartVTK：导出流体粒子 VTK（ParaView 可视化）
- PartVTK：导出边界粒子 VTK
- MeasureTool：探针数据提取
- compute_metrics：与 ground truth 对比（如果存在）
- 打开 ParaView 显示结果

### Phase 5 — Review(results) — Analysis Loop
用户查看后处理结果。可以：
- **approve** → 工作流结束
- **分析请求** → AnalyzeExecutor（LLM 驱动）：
  1. LLM 根据用户请求 + 后处理技能文件，规划分析步骤
  2. 执行 `run_postprocess`（PartVTK/IsoSurface/ComputeForces 等）
  3. 执行 `run_analysis`（Python 脚本解析 CSV、计算导出量、绘图）
  4. 返回结果 → 回到 Review(results) 循环
- **question** → Q&A
- **full_replan** → 警告用户代价高，确认后回到 Planning

---

## 工具分工

### 预处理工具（7 个）
| 工具 | 职责 |
|------|------|
| `set_geometry` | 替换 `<geometry>` 块 |
| `modify_xml` | 修改物理/执行参数（15 个参数） |
| `generate_points_file` | 生成探针点文件 |
| `run_gencase` | 生成粒子配置 |
| `run_simulation` | 运行 DualSPHysics 求解器 |
| `run_measuretool` | 探针数据提取 |
| `compute_metrics` | RMSE/相关性计算 |

### 后处理工具（2 个 MCP 工具，包装 8 个 CLI 二进制）
| 工具 | 职责 |
|------|------|
| `run_postprocess` | 通用包装器：partvtk, partvtkout, isosurface, computeforces, flowtool, boundaryvtk, floatinginfo, measuretool |
| `run_analysis` | 执行 Python 分析脚本（numpy/matplotlib/pandas） |

---

## 关键实现细节

### GPU 自动检测
SimExecutor 通过 `shutil.which("nvidia-smi")` 检测 GPU 可用性，自动选择 CPU 或 GPU 求解器。

### AnalyzeExecutor 双模式
- **默认模式**（`ReviewResult` 触发）：确定性，无 LLM 调用
- **分析模式**（`AnalysisRequest` 触发）：LLM 规划分析步骤，返回 JSON `{"steps": [...]}`
  - `{"type": "postprocess", "tool_name": "...", "args": [...]}`
  - `{"type": "python", "code": "...", "description": "..."}`

### 环境变量
- `OPENAI_API_KEY`：必需
- `PLANNER_MODEL`：SimulationPlanner 模型（默认 `gpt-4o`）
- `PATCH_MODEL`：PatchExecutor 模型（默认 `gpt-4o`）
- `INTENT_MODEL`：intent classification + Q&A（默认 `gpt-4o-mini`）
- `ANALYSIS_MODEL`：AnalyzeExecutor 分析规划（默认 `gpt-4o`）

---

## 下一步

1. **生成 ground truth**：用默认参数跑完整模拟，MeasureTool 输出存为 `cases/ground_truth/PointsMeasure.csv`
2. **完善 skill file**：请领域专家扩充材料原型表
3. **推送到 GitHub**：注意硬编码绝对路径
4. **Agent 2 + 优化循环**：后续实现
