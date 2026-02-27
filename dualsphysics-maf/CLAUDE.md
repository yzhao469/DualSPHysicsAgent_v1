# DualSPHysics MAF — Project Notes for Claude

## 项目位置
```
/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf/
```
Python venv: `.venv/`
Run with: `.venv/bin/python`

---

## 已完成文件

| 文件 | 状态 |
|------|------|
| `mcp_server/config.py` | ✅ 完成 |
| `mcp_server/__init__.py` | ✅ |
| `mcp_server/tools/__init__.py` | ✅ |
| `mcp_server/tools/_subprocess.py` | ✅ 共享异步子进程 helper |
| `mcp_server/tools/xml_modifier.py` | ✅ 含非标准 XML 预处理（见下） |
| `mcp_server/tools/run_gencase.py` | ✅ |
| `mcp_server/tools/run_simulation.py` | ✅ |
| `mcp_server/tools/run_measuretool.py` | ✅ |
| `mcp_server/tools/metrics.py` | ✅ |
| `mcp_server/server.py` | ✅ FastMCP，5 个工具 |
| `agents/__init__.py` | ✅ |
| `agents/simulation_agent.py` | ✅ Agent 1，已修正 API (`client=` 不是 `chat_client=`) |
| `cases/CaseDebrisFlow2D_Def.xml` | ✅ 从 examples/ 复制 |
| `cases/CaseDebrisFlow2D_Points.txt` | ✅ 6 个探针点 |
| `cases/ground_truth/` | ⬜ 目录存在（含 `.gitkeep`），CSV 未生成（留待后续） |
| `main.py` | ✅ Agent 1 测试入口，含 `TimeMax=0.5` smoke 参数 |
| `requirements.txt` | ✅ |
| `.gitignore` | ✅ 排除 `.venv/`、`runs/`、`__pycache__/`、`*.log`、`.env` |
| `README.md` | ✅ 供协作者使用的完整设置文档 |

---

## Smoke Test 结果

### 运行参数
```python
dp=0.015, Visco=0.1, DensityDT=3, DensityDTvalue=0.1,
coefh=0.91924, cflnumber=0.1,
TimeMax=0.5, TimeOut=0.1   # 5 个输出步，smoke 用
```

### 各步结果
| 步骤 | 结果 |
|------|------|
| `modify_xml` | ✅ 正常，dp/TimeMax 已写入 |
| `run_gencase` | ✅ 0.1s，4984 粒子（fluid=3264, bound=1720） |
| `run_simulation` (CPU) | ✅ **107s** 完成，生成 6 个 Part_*.bi4 |
| `run_measuretool` | ✅ rc=0，输出 `PointsMeasure_Rhop.csv` + `PointsMeasure_Vel.csv` |
| `compute_metrics` | ✅ ground_truth 不存在时正确返回 `{"status": "no_ground_truth"}` |
| Agent 1 端到端 | ✅ 通过（见下方 Agent 1 端到端结果） |

---

## Stub Chrono Libraries

DualSPHysics CPU/GPU 二进制在 `bin/linux/` 里没有附带：
- `libdsphchrono.so`
- `libChronoEngine.so`
- `libChronoEngine_parallel.so`

**解决方案**：在 `bin/linux/` 创建了三个 stub `.so`（空函数体汇编），包含二进制所需的 31 个 Chrono C++ 符号。DebrisFlow2D 不调用刚体模拟功能，所以 stub 不会被实际调用。

验证：
```bash
env LD_LIBRARY_PATH=/home/danrong/projects/DualSPHysics_NN_v5.0.1/bin/linux \
  .../DualSPHysics5.0_NNewtonianCPU_linux64
# 正常输出版权信息，加载成功
```

`run_simulation.py` 通过 `os.environ.copy()` + 设置 `LD_LIBRARY_PATH=BIN_DIR` 传递给子进程。

---

## 关键实现细节

### XML 预处理（非标准 XML）
`CaseDebrisFlow2D_Def.xml` 含两处非标准内容，标准 Python ElementTree 无法直接解析：
1. 三连横线注释 `<!---Phase 1--->` → 注释内容含 `--`，违反 XML 规范
2. 属性值内的未转义 `<`/`>` (如 `comment="<1 for shear thinning"`)

`xml_modifier.py` 在解析前用正则预处理修复这两个问题。写出的 XML 是标准 XML，GenCase 可以正常读取。

### agent_framework RC1 正确 API
```python
Agent(client=AnthropicClient(...), ...)   # 不是 chat_client=
agent.run(messages, tools=[mcp_tool])      # tools 在 run() 里传
MCPStdioTool(..., cwd=BASE)               # cwd 通过 **kwargs 传给 StdioServerParameters
```
venv 中 `opentelemetry-semantic-conventions-ai` 需固定为 `==0.4.13`（0.4.14 有 API 破坏）。

### MeasureTool Points 文件格式（已踩坑）
每个探针点用一个 `POINTSLIST` 块，格式为 origin / step / count：
```
POINTSLIST
0.4 1.0 0.5    <- origin (x y z)
0 0 0          <- step (单点时全为0)
1 1 1          <- count (单点时全为1)
```
MeasureTool 输出两个 CSV：`<stem>_Vel.csv` 和 `<stem>_Rhop.csv`，用 `;` 分隔，前3行是位置元数据（以 ` ;` 开头，需跳过）。

### 可配置的 XML 参数（modify_xml 支持）
`dp`, `coefh`, `cflnumber`, `Visco`, `DensityDT`, `DensityDTvalue`,
`TimeMax`, `TimeOut`, `visco_nn`, `tau_yield`, `HBP_m`, `HBP_n`

### xml_modifier.py — 自动创建输出目录（已修复）
写出 XML 前加了 `Path(output_xml).parent.mkdir(parents=True, exist_ok=True)`。
修复前 agent 会在 `modify_xml` 上反复重试（因目录不存在而失败），导致 XML 散落在项目根目录。

---

## Agent 1 端到端结果（2026-02-24）

```
ANTHROPIC_API_KEY=... .venv/bin/python main.py
```

| 步骤 | 结果 |
|------|------|
| `modify_xml` | ✅ 所有 8 个参数写入 |
| `run_gencase` | ✅ 4984 粒子（bound=1720, fluid=3264） |
| `run_simulation` (CPU) | ✅ **69s** 完成，7858 步，6 个 Part 文件 |
| `run_measuretool` | ✅ `PointsMeasure_Rhop.csv` + `PointsMeasure_Vel.csv` |
| `compute_metrics` | ⚠️ `no_ground_truth`（预期，CSV 尚未生成） |

**已知问题（待修复）：**
- Agent 生成的时间戳用了错误年份（`20250519` 而非 `20260224`）——agent_framework 内部时钟问题
- 修复 `xml_modifier.py` 前，run 目录被错误放在项目根目录而非 `runs/` 下

---

## 下一步

1. **生成 ground truth**：用默认参数跑一次完整模拟（`TimeMax=5.0`），把 MeasureTool 输出存为 `cases/ground_truth/PointsMeasure.csv`
   - 方案 A：用默认参数的高精度模拟结果作为参考（最简单，随时可做）
   - 方案 B：使用真实实验测量数据（需要外部数据）

2. **推送到 GitHub**：`.gitignore` 和 `README.md` 已就绪；注意 `config.py` 和 `simulation_agent.py` 里有硬编码的绝对路径，协作者需手动修改

3. **Agent 2 + 优化循环**（后续实现）
