# DualSPHysics MAF — Project Notes for Claude

## 项目位置
```
/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf/
```
Python venv: `.venv/`
Run with: `.venv/bin/python`

---

## 架构（2026-03-01 重构 — Workflow-Based + HITL）

**核心模式**：LLM 只做推理（返回结构化 SimulationPlan JSON），
Python 代码确定性地编排所有 MCP 工具调用。

```
main.py → WorkflowBuilder
  ├─ SimulationCoordinator (Executor) — 确定性编排器
  └─ AgentExecutor(SimulationPlanner) — GPT-4o 推理 + 结构化输出
```

HITL 通过 workflow `request_info` / `response_handler` 模式实现：
1. Coordinator 调用 `ctx.request_info(ReviewRequest(...))`
2. Workflow 暂停，main.py 事件循环提示用户 `input()`
3. `workflow.run(responses={request_id: user_reply})` 恢复

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

### Workflow + Agent
| 文件 | 状态 | 说明 |
|------|------|------|
| `agents/__init__.py` | ✅ | |
| `agents/schemas.py` | ✅ | Pydantic 模型：SimulationPlan, PhysicsParams, ReviewRequest |
| `agents/coordinator.py` | ✅ | SimulationCoordinator (Executor)：确定性编排 + HITL |
| `agents/simulation_agent.py` | ✅ | SimulationPlanner (Agent)：OpenAI GPT-4o + 结构化输出 |
| `agents/prompts/simulation_agent.j2` | ✅ | 简化模板：仅几何 DSL + 物理推理 + JSON schema |
| `agents/tools/__init__.py` | ✅ | |
| `agents/tools/visualize_geometry.py` | ✅ | ParaView VTK 可视化（WSL2 兼容），由 coordinator 直接调用 |

### 已删除
| 文件 | 说明 |
|------|------|
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

## Workflow 四阶段

### Phase 1 — 自然语言 → LLM 推理
Coordinator 收到场景描述 → 发给 AgentExecutor → GPT-4o 返回 SimulationPlan JSON

### Phase 2 — HITL 审核 #1（执行前）
Coordinator 展示几何 XML、参数表、探针坐标。用户可以批准或请求修改（修改 → 回到 Phase 1）。

### Phase 3 — 构建 & 可视化
Coordinator 确定性调用：
`set_geometry` → `modify_xml` → `generate_points_file` → `run_gencase` → `visualize_geometry`（ParaView）

### Phase 4 — HITL 审核 #2（GenCase 后）
用户查看 ParaView 可视化，批准后 Coordinator 执行：
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
