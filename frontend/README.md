# 天枢智航运行控制台

Vue 3、TypeScript、CesiumJS 与 ECharts 实现的中文操作台。所有飞行位置、运行指标、趋势和事件结果来自后端仿真快照，没有随机前端数据或预制演示指标。

## 运行

在项目根目录启动后端（默认 8011），然后在此目录执行：

```powershell
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`。开发服务器将 `/api` HTTP 与 WebSocket 请求转发到后端；地址可在启动前通过 `TS_API_TARGET` 环境变量覆盖。

```powershell
npm run build
```

构建前自动将 Cesium Workers、Assets、Widgets 和 ThirdParty 资源复制到本地静态目录。生产部署必须将 `/api`（包括 `/api/ws` 升级请求）代理至 FastAPI；单独运行静态 `vite preview` 不提供后端代理。

## 演示操作

1. 点击“生成 100 机演示场景”，等待后端生成城市、任务和飞行器。该操作保持暂停状态。
2. 选择时间倍率并启动仿真。右侧指标、底部趋势与事件时间线随服务端数据更新。
3. 自动演示依次触发四种情境；也可手动选择航路拥堵、雷暴、飞行器故障或临时管制。故障选项仅列出适用状态的飞行器。
4. 单击场景飞行器或使用编号列表查看速度、高度、电量、优先级、目的地、剩余航程和延误。选中飞行器显示规划线。
5. 暂停后可单步推进；导出报告获得实际运行指标、历史与事件处理结果。

Cesium 使用本地 ENU 到地球固定坐标的变换，显示程序化建筑、航路、起降点、备降点、飞行器轨迹、管制棱柱、天气区域与冲突位置。未使用 Cesium ion、在线底图或外部城市瓦片，原始 Cesium credits 保留。该城市是仿真模型，并非真实测绘城市。

## 代码组织

- `services/api.ts`：HTTP 错误处理、超时与报告下载。
- `stores/simulation.ts`：快照状态、HTTP/WS 初始化、指数重连、命令执行。
- `types/simulation.ts`：快照结构及中文状态映射。
- `components/CityScene.vue`：按 ID 更新 Cesium 实体与相机交互。
- `components/ControlPanel.vue`：运行指标、控制命令、事件注入和单机详情。
- `components/MetricsChart.vue`：最近 240 个实际历史采样点。
- `components/EventTimeline.vue`：最新 100 条后端事件及结构化处理结果。

实时协议为 `{type:"snapshot",sequence,data}`。新连接收到完整城市；后续快照省略 `environment` 时保留旧城市，显式 `null` 表示没有城市。断线期间保留最后状态，显示重连提示并禁用仿真写入按钮。重新连接后采用新的完整快照。

右侧九项统计的口径由后端统一定义；前端只做单位转换（米到千米、比例到百分比）和显示舍入。应急处理耗时采用服务端实际测量的毫秒，仿真时钟采用服务端秒数。
