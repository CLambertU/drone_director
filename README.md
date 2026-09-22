# 天枢智航——城市低空交通智能规划与自主协同系统

面向城市低空经济场景的无人机交通智能规划与仿真平台，构建
**“感知 → 分析 → 决策 → 执行 → 反馈”** 闭环：城市三维环境建模、航路网络自动规划、
多机任务分配、动态流量管理、冲突检测与解脱、气象/管制/故障事件注入、应急备降、
动态重规划与三维可视化监控。

> 工程原则：**正确性 > 稳定性 > 可演示性 > 算法复杂度 > UI**。
> MVP 使用可解释的传统算法（A*、规则解脱、优化调度），并为 GNN / PPO / MAPPO
> 预留清晰的算法接口；所有指标必须来自真实仿真数据，禁止硬编码演示结果。

---

## 一、技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.13 · FastAPI · WebSocket · Pydantic v2 |
| 算法 | NumPy · NetworkX · A*/Dijkstra · 多目标代价 ·（预留 GNN/RL 接口） |
| 仿真 | 独立固定步长引擎，仿真时间与真实时间解耦（默认 10×） |
| 前端 | Vue 3 · TypeScript · Vite · ECharts · CesiumJS（第七阶段引入） |
| 数据 | MVP：线程安全内存仓储（Repository 抽象）；后续可替换 SQLite / PostgreSQL+PostGIS |
| 测试 | pytest · FastAPI TestClient |

## 二、目录结构

```
dorne_competition/
├── backend/            # FastAPI 适配层（HTTP/WS），不含业务规则
│   ├── api/            # 路由：aircraft / waypoints / routes / missions / weather / restrictions / events / system
│   ├── config/         # 集中配置（pydantic-settings，环境变量前缀 TS_）
│   ├── app.py          # 应用工厂与 ASGI 入口
│   ├── seed.py         # Demo 种子数据加载
│   ├── exceptions.py   # 统一异常与错误响应
│   └── logging_config.py
├── core/               # 共享内核（不依赖 Web 框架）
│   ├── models/         # 领域模型与枚举（8 类实体 + 几何类型）
│   ├── coords/         # 米制 ENU ↔ WGS84 坐标转换层（第二阶段）
│   └── repository/     # Repository 抽象 + 内存实现 + 注册表
├── algorithms/         # 纯算法库，可独立单测（规划/流量/冲突/解脱/应急/调度）
├── simulation/         # 仿真引擎（engine/environment/aircraft/weather/airspace/events）
├── frontend/           # Vue3 + CesiumJS（第七阶段）
├── data/               # 种子数据、后续 SQLite 文件
├── docs/               # 架构与 API 文档
├── scripts/            # 启动/测试脚本（PowerShell）
├── tests/              # pytest 单元与集成测试
└── pyproject.toml
```

依赖方向（只允许上层依赖下层）：
`backend → core ← algorithms ← simulation`，**算法层与仿真层不 import FastAPI**。

## 三、快速开始

### 1. 环境准备（使用 uv）

```powershell
uv venv
uv pip install -e ".[dev]"
```

当前仓库 `.venv` 已包含全部运行期依赖，也可直接使用。

### 2. 启动后端

```powershell
.\scripts\run_backend.ps1
# 或直接运行启动文件（端口读取 TS_PORT 配置，默认 8011）
.venv\Scripts\python.exe -m backend.app
# 或显式指定：.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8011 --reload
```

- 交互式 API 文档（Swagger）：<http://127.0.0.1:8011/docs>
- 健康检查：<http://127.0.0.1:8011/api/health>

### 3. 加载 Demo 数据

```powershell
# 启动后调用（会清空当前数据并写入 11 个航路点 / 6 条航路 / 8 架飞机 / 3 个任务）
curl.exe -X POST http://127.0.0.1:8011/api/system/seed
# 或设置环境变量让服务启动时自动加载：
$env:TS_SEED_ON_STARTUP="true"
```

### 4. 运行测试

```powershell
.\scripts\run_tests.ps1
# 或：.venv\Scripts\python.exe -m pytest
```

## 四、HTTP API（第一阶段）

所有实体均提供 `GET 列表 / POST 创建 / GET 详情 / PUT 更新 / DELETE`：

| 资源 | 前缀 |
|---|---|
| 飞行器 | `/api/aircraft` |
| 航路点 | `/api/waypoints` |
| 航路 | `/api/routes` |
| 任务 | `/api/missions` |
| 气象区域 | `/api/weather` |
| 空域管制 | `/api/restrictions` |
| 动态事件 | `/api/events` |

系统与环境接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/system/summary` | 各实体当前数量 |
| POST | `/api/system/seed` | 加载 Demo 数据（实体 + 程序化城市 + 航路网） |
| POST | `/api/system/reset` | 清空全部数据 |
| GET | `/api/environment/summary` | 城市边界、建筑数量、栅格占用率 |
| GET | `/api/environment/buildings` | 全部建筑（footprint + 高度） |
| GET | `/api/environment/route-network` | 航路有向图节点与航段（供三维可视化） |
| GET | `/api/environment/validation` | 航路段穿越建筑校验 |
| POST | `/api/environment/rebuild` | 按当前仓储实体重建城市与航路网 |

错误响应统一格式：

```json
{ "error": { "code": "not_found", "message": "飞行器 不存在: ACX", "details": {} } }
```

## 五、配置说明（环境变量，前缀 `TS_`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TS_HOST` / `TS_PORT` | 127.0.0.1 / 8011 | 监听地址 |
| `TS_LOG_LEVEL` | INFO | 日志级别 |
| `TS_SEED_ON_STARTUP` | false | 启动时自动加载种子数据 |
| `TS_COST_WEIGHT_DISTANCE` | 1.0 | A* 距离代价权重 w1 |
| `TS_COST_WEIGHT_RISK` | 2.0 | 风险代价权重 w2 |
| `TS_COST_WEIGHT_CONGESTION` | 1.5 | 拥堵代价权重 w3 |
| `TS_COST_WEIGHT_ENERGY` | 0.8 | 能耗代价权重 w4 |
| `TS_COST_WEIGHT_WEATHER` | 3.0 | 天气代价权重 w5 |
| `TS_CONFLICT_HORIZONTAL_SEPARATION_M` | 30 | 水平安全间隔（米） |
| `TS_CONFLICT_VERTICAL_SEPARATION_M` | 15 | 垂直安全间隔（米） |
| `TS_CONFLICT_TIME_WINDOW_S` | 10 | 冲突时间窗（秒） |
| `TS_SIMULATION_DEFAULT_SPEED` | 10 | 仿真倍速（现实 1s = 仿真 10s） |
| `TS_SIMULATION_TICK_SECONDS` | 1.0 | 仿真步长（仿真秒/tick） |

## 六、坐标约定

仿真与算法内部**只使用局部米制 ENU 坐标**（x 东 / y 北 / z 离地高度），
经纬度转换统一在 `core/coords` 完成（第二阶段实现），
前端 Cesium 仅在 API 边界做 WGS84 转换。

## 七、迭代路线

- [x] **阶段一**：项目骨架、领域模型、仓储抽象、基础 API、测试与种子数据
- [x] **阶段二**：城市三维环境（ENU/WGS84 转换、占用栅格、建筑碰撞、确定性城市生成）与 NetworkX 航路有向图
- [ ] 阶段三：A* 多目标航路规划（w1~w5 可配置权重、禁飞区、容量、重规划）
- [ ] 阶段四：仿真引擎、无人机飞行模型与任务调度
- [ ] 阶段五：多机冲突检测与规则式冲突解脱
- [ ] 阶段六：天气、临时空域、故障备降与动态事件流水线
- [ ] 阶段七：Vue3 + CesiumJS 三维可视化
- [ ] 阶段八：WebSocket 实时增量同步
- [ ] 阶段九：100 机完整自动 Demo（拥堵→雷暴→故障→冲突）
- [ ] 阶段十：测试、性能优化与比赛展示打磨
