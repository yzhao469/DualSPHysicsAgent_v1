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
| `cases/ground_truth/` | ⬜ 目录存在，CSV 未生成（留待后续） |
| `main.py` | ✅ Agent 1 测试入口，含 `TimeMax=0.5` smoke 参数 |
| `requirements.txt` | ✅ |

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
| Agent 1 端到端 | ⬜ 未测试 |

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

---

## 下一步

1. **Agent 1 端到端测试**：设置 `ANTHROPIC_API_KEY`，运行 `main.py`
   ```bash
   ANTHROPIC_API_KEY=... .venv/bin/python main.py
   ```

2. **生成 ground truth**：用默认参数跑一次完整模拟（TimeMax=5.0），把 MeasureTool 输出存为 `cases/ground_truth/PointsMeasure.csv`

3. **Agent 2 + 优化循环**（计划范围外，后续实现）
