# 第三阶段：可解释的多项加权 A* 航路规划

本阶段实现静态环境快照上的规划与重新规划。算法没有训练或调用 GNN、PPO、MAPPO；`PathPlanner` 协议允许以后接入使用相同输入输出的实现。

## 调用与返回

```python
from algorithms.path_planning import CostWeights, PlanningContext, plan_path

result = plan_path(
    source="WP01",
    target="WP09",
    context=PlanningContext(
        graph=network.graph,
        city=city,
        restrictions=restrictions,
        weather=weather,
        speed_mps=15,
        max_distance_m=8000,
    ),
    weights=CostWeights(distance=1, risk=2, congestion=1.5, energy=0.8, weather=3),
)
```

输入图必须是没有平行边的有向图，节点 `position` 是局部 ENU 米制 `Position3D`。边使用 `distance`、`risk_level`、`capacity`、`current_flow`、`status`；未提供时使用几何距离、0、10、0、`open`。生产调用应使用城市航路网络生成的完整属性。

`PlanningResult` 返回 `node_ids`、`positions`、`distance_m`、`estimated_duration_s`、`total_cost`、`cost_breakdown`、`algorithm` 和 `explanation`。`cost_breakdown` 是各项已经乘权重后的贡献，其和等于总成本。

HTTP 入口为 `POST /api/planning/path`。请求包含 `source`、`target`，可选 `weights`、`speed_mps`、`max_distance_m`、`respect_capacity`、`blocked_edges` 和 `dimension`。`dimension="2d"` 只搜索起点所在高度层，`"3d"` 允许跨高度层；均保留真实高度做障碍与管制校验。响应额外给出 `environment_version`，用于识别规划依据的环境版本。

## 代价定义与最优性范围

每条边的长度 `L = max(几何三维长度, 声明长度) / 1000`，单位换算为千米。风险 `r∈[0,1]`，利用率 `u=current_flow/capacity`，上升高度 `H=max(0,z_end-z_start)/1000`。

```text
distance   = w_distance   × L
risk       = w_risk       × L × r
congestion = w_congestion × L × u
energy     = w_energy     × (L + 4H)
weather    = w_weather    × L × p_weather
edge_cost  = distance + risk + congestion + energy + weather
```

权重必须是非负有限数，允许某一项或全部为零。风险、拥堵、气象按距离累计，减少人为航段分割对总成本的影响。长度与爬升采用固定的 1000 米尺度；不是根据当前候选路线动态归一化。

`energy` 是用于比较航路的几何能耗代理，爬升系数 4 是 MVP 的明确假设，不能解释为瓦时或真实电池消耗。风向、风速影响气象项；尚未实现依赖机型的风阻与电池物理模型。

气象惩罚采用整条边的保守暴露量：只要边与天气区域相交便计入，重叠区域取最大惩罚，不重复累计。风向为气象来风方向（0° 北、90° 东）：

```text
p_weather = (逆风分量 + 0.25 × 横风分量) / speed_mps
          + 降水惩罚 + max(0, (5000 - visibility_m) / 5000)
```

小雨、雨、雪、冰雹惩罚分别为 0.25、0.75、1、2；无降水为 0。顺风不产生负成本。雷暴直接阻断航段，不使用软惩罚绕过。

A* 启发值为 `w_distance × 到终点的三维直线距离 / 1000`。由于每条边的距离至少等于两端点直线距离，其他成本非负，该启发值不会高估剩余成本。`w_distance=0` 时启发值为零，搜索退化为 Dijkstra。最优性仅针对本次快照中通过硬约束的图及上述加权目标，不代表所有连续空间轨迹中的最优路线。

## 硬约束与航程

以下航段在搜索之前被剔除：

- `status=closed` 或列于 `blocked_edges`。
- 开启容量检查时，`current_flow >= capacity`。
- 穿过建筑、超出城市边界或低于地面；采用城市的精确线段碰撞检查。
- 与激活管制区的闭合三维棱柱相交，包括接触边界；上升、下降段按照实际高度交点裁剪。
- 水平投影与雷暴区域相交。当前天气实体没有高度带，因此雷暴保守地阻断所有高度层。

起点与终点同样进行空间安全检查；只有端点安全时 `source=target` 才返回零长度路径。安全间隔使用城市碰撞接口的默认参数，尚未按机型配置机体包络。

如果加权最优路径超过 `max_distance_m`，同一可行图上会执行最短距离 Dijkstra。若最短距离也超限，返回 `range_limit`。否则返回 `algorithm="dijkstra_range_fallback"` 并明确说明：这条路径保证在给定航程内，但**不保证是航程约束下加权成本最小的路径**。多标签资源约束最短路径尚未实现。

`estimated_duration_s=distance_m/speed_mps`，是固定地速估算，不包含等待、排队和气象导致的实际速度变化。`max_distance_m` 由调用方提供；本阶段尚未把电池余量换算为可飞距离。

## 动态重规划与接口责任

调用方在同一状态锁下提供一致快照，算法复制图和天气、管制数据并保持搜索期间代价不变；城市对象按只读快照使用。调用本身不修改航路、不增加流量、不预留容量。

天气、容量、管制或航段状态改变后，以新快照再次调用即可重新规划；`blocked_edges` 可以额外排除指定方向的边。对称封闭需同时传入两个方向。自动事件触发、飞机当前航段接续、原路径撤销和容量原子预留由后续仿真调度阶段负责。

失败使用 `PlanningError`，包含 `reason` 和 `details`：

| reason | 含义 |
|---|---|
| `invalid_context` | 非有限或越界数值、缺失节点位置、错误图类型等 |
| `unknown_waypoint` | 起点或终点不存在于本次候选图 |
| `unsafe_endpoint` | 起终点在障碍、雷暴或管制区内 |
| `no_path` | 硬约束过滤后不连通，附剔除航段原因计数 |
| `range_limit` | 所有可行路径都超过给定航程 |

## 验证

```powershell
.\.venv-runtime\Scripts\python.exe -m pytest tests/test_path_planning.py tests/test_planning_api.py
```

测试覆盖独立 Dijkstra 代价对照、风险绕行、容量与封闭、窄建筑和边界、三维管制交点、天气来风方向与重叠区域、动态快照重新规划、零长度路径、航程回退标识、不可达以及非有限/负权重和上下文数值拒绝。
