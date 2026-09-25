import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { GlobalFonts } from "@napi-rs/canvas";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "D:/dorne_competition";
const skillDir = "C:/Users/18980/.codex/plugins/cache/openai-primary-runtime/presentations/26.923.10815/skills/presentations";
const buildDir = path.join(workspaceDir, ".codex-build");
const finalPath = path.join(workspaceDir, "output", "天枢智航_算法设计答辩.pptx");
const coverPath = path.join(buildDir, "tianshu-cover.png");
const fontFamily = "Microsoft YaHei";

const registered = GlobalFonts.registerFromPath("C:/Windows/Fonts/msyh.ttc", fontFamily);
if (!registered) throw new Error("Could not register Microsoft YaHei for rendering");

const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools/artifact_tool_utils.mjs"),
).href);

const W = 1280;
const H = 720;
const C = {
  bg: "#0B1422",
  bg2: "#101E30",
  white: "#F3F7FB",
  muted: "#B2C1D0",
  dim: "#8095A9",
  cyan: "#49D3E4",
  blue: "#64A9FF",
  amber: "#FFC477",
  red: "#F47D7D",
  rule: "#2B4055",
};

const presentation = Presentation.create({ slideSize: { width: W, height: H } });
let shapeCounter = 0;

function text(slide, value, left, top, width, height, options = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    name: options.name || `text-${++shapeCounter}`,
    position: { left, top, width, height },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  s.text = value;
  s.text.style = {
    typeface: fontFamily,
    fontSize: options.size ?? 24,
    bold: options.bold ?? false,
    color: options.color ?? C.white,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "middle",
    autoFit: "shrinkText",
    wrap: "square",
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return s;
}

function rect(slide, left, top, width, height, fill, name = undefined) {
  return slide.shapes.add({
    geometry: "rect",
    ...(name ? { name } : {}),
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function rule(slide, left, top, width, color = C.rule, height = 1) {
  return rect(slide, left, top, width, height, color);
}

function addSlide() {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  return slide;
}

function header(slide, titleText) {
  text(slide, titleText, 72, 44, 1136, 66, { size: 43, bold: true, name: "slide-title" });
  rect(slide, 72, 126, 58, 4, C.cyan, "title-accent");
}

function notes(slide, noteText) {
  slide.speakerNotes.textFrame.setText(noteText);
}

// 1. Cover
{
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  const coverBytes = new Uint8Array(await fs.readFile(coverPath));
  slide.images.add({
    blob: coverBytes,
    contentType: "image/png",
    alt: "黄昏城市中的低空无人机航路网络概念图",
    fit: "cover",
    position: { left: 0, top: 0, width: W, height: H },
  });
  text(slide, "天枢智航", 82, 260, 540, 100, { size: 70, bold: true, name: "cover-title" });
  text(slide, "城市低空交通智能规划与自主协同系统", 86, 370, 560, 54, { size: 29, color: "#D7E8F6", name: "cover-subtitle" });
  rect(slide, 86, 448, 72, 4, C.cyan);
  text(slide, "大赛答辩  ·  算法设计与系统验证", 86, 478, 550, 44, { size: 24, color: C.muted });
  notes(slide, "项目名称与定位据 README.md。封面主视觉为本项目答辩专用概念插画。\n项目核心算法是可解释的加权 A*、连续轨迹冲突检测与规则解脱；当前没有已训练的 GNN 或强化学习模型。");
}

// 2. Problem framing
{
  const slide = addSlide();
  header(slide, "城市低空规划要同时回答三个问题");
  const cols = [
    { x: 72, n: "01", title: "哪条航路可飞", body: "建筑与边界\n临时管制空域\n航路容量与雷暴" },
    { x: 463, n: "02", title: "怎样权衡路线", body: "距离与风险\n拥堵、气象\n爬升能耗代理" },
    { x: 854, n: "03", title: "如何保持间隔", body: "未来轨迹相交\n同一时刻水平与垂直\n间隔同时不足" },
  ];
  for (let i = 0; i < cols.length; i++) {
    const c = cols[i];
    text(slide, c.n, c.x, 195, 70, 54, { size: 34, bold: true, color: C.cyan });
    text(slide, c.title, c.x, 252, 310, 44, { size: 28, bold: true });
    text(slide, c.body, c.x, 319, 318, 140, { size: 24, color: C.muted, valign: "top" });
    if (i < 2) rect(slide, c.x + 345, 198, 1, 270, C.rule);
  }
  rule(slide, 72, 520, 1136, C.rule, 1);
  text(slide, "设计原则：硬约束先定安全可行域，再优化路线代价，并对未来轨迹做全机复检", 72, 550, 1120, 86, { size: 26, bold: true, color: C.white });
  notes(slide, "项目约束与路径规划输入输出见 docs/path-planning.md；冲突阈值与连续轨迹模型见 algorithms/conflict_detection/models.py。距离、风险、拥堵、能耗与气象不是同一量纲，因此通过显式权重比较；建筑、空域与容量则作为硬约束处理。");
}

// 3. Algorithm loop
{
  const slide = addSlide();
  header(slide, "算法闭环：从环境快照到安全执行");
  const stages = [
    ["一致快照", "航路图\n天气与空域\n当前流量"],
    ["硬约束筛边", "几何碰撞\n容量与封闭\n雷暴、管制"],
    ["加权 A*", "最小化五项\n综合边代价\n返回代价分解"],
    ["连续预测", "分段线性轨迹\n共同时间窗\n精确检验间隔"],
    ["规则解脱", "生成候选动作\n逐机全机复检\n按代价排序"],
    ["执行与复核", "推进仿真\n事件更新状态\n重新规划"],
  ];
  const x0 = 72;
  const colW = 164;
  const gap = 29;
  stages.forEach(([titleText, body], i) => {
    const x = x0 + i * (colW + gap);
    text(slide, String(i + 1).padStart(2, "0"), x, 194, colW, 43, { size: 31, bold: true, color: C.cyan });
    text(slide, titleText, x, 246, colW + 10, 50, { size: 23, bold: true });
    text(slide, body, x, 312, colW, 128, { size: 20, color: C.muted, valign: "top" });
    if (i < stages.length - 1) text(slide, "→", x + colW + 1, 256, gap - 2, 44, { size: 28, bold: true, color: C.dim, align: "center" });
  });
  rule(slide, 72, 484, 1136, C.rule, 1);
  text(slide, "环境版本或任务状态变化", 92, 526, 350, 44, { size: 23, bold: true, color: C.amber });
  text(slide, "→", 440, 526, 70, 44, { size: 30, bold: true, color: C.cyan, align: "center" });
  text(slide, "读取新快照，再规划并复检", 522, 526, 615, 44, { size: 23, bold: true });
  text(slide, "规划器本身只读快照，不在搜索过程中修改流量或预留容量", 92, 590, 1060, 34, { size: 20, color: C.muted });
  notes(slide, "闭环依据 README.md 与 docs/path-planning.md：调用方在一致状态锁下提供快照；规划过程不预留容量，状态改变后以新快照重规划。冲突规则模块对候选轨迹逐架复检，运行时按每个仿真步复核预测与实际运动。完整演示的事件时间线见 docs/demo.md。");
}

// 4. Multi-criteria A*
{
  const slide = addSlide();
  header(slide, "加权 A*：把运行目标写进每条边的代价");
  text(slide, "J(e) = w_d·L + w_r·L·r + w_c·L·u + w_e·(L + 4H) + w_w·L·p_w", 72, 161, 1136, 62, { size: 27, bold: true, color: C.white, align: "center" });
  text(slide, "L：三维航段长度（km）；H：净爬升（km）；r：风险等级；u：流量 / 容量；p_w：气象暴露惩罚", 72, 231, 1136, 42, { size: 20, color: C.muted, align: "center" });
  const terms = [
    ["距离", "w_d · L", "缩短路线"],
    ["风险", "w_r · L · r", "按航程累计风险"],
    ["拥堵", "w_c · L · u", "容量越紧代价越高"],
    ["能耗代理", "w_e · (L + 4H)", "显式惩罚爬升"],
    ["气象", "w_w · L · p_w", "逆风、横风、降水与能见度"],
  ];
  terms.forEach(([label, formula, desc], i) => {
    const x = 72 + i * 227;
    text(slide, label, x, 326, 205, 44, { size: 25, bold: true, color: i === 3 ? C.amber : C.cyan });
    text(slide, formula, x, 384, 205, 52, { size: 22, bold: true });
    text(slide, desc, x, 453, 205, 86, { size: 20, color: C.muted, valign: "top" });
    if (i < terms.length - 1) rect(slide, x + 213, 324, 1, 214, C.rule);
  });
  rule(slide, 72, 570, 1136, C.rule, 1);
  text(slide, "默认权重  (w_d, w_r, w_c, w_e, w_w) = (1, 2, 1.5, 0.8, 3)", 72, 592, 1136, 44, { size: 22, bold: true, align: "center" });
  text(slide, "能耗为路线比较代理值；爬升系数 4 是工程假设，不等于电池电量", 72, 644, 1136, 30, { size: 18, color: C.muted, align: "center" });
  notes(slide, "代价公式、长度尺度、风险范围、拥堵利用率和默认权重见 algorithms/path_planning/astar.py 与 algorithms/path_planning/models.py，也详述于 docs/path-planning.md。能耗按距离加 4 倍爬升构成，仅用于比较，不可解释为瓦时或真实电池消耗。天气项按整条边的保守暴露量计算，重叠天气区取最大惩罚。");
}

// 5. Hard constraints and heuristic
{
  const slide = addSlide();
  header(slide, "硬约束先筛边，启发值再保证搜索方向");
  text(slide, "不可行航段在搜索前剔除", 72, 170, 630, 45, { size: 27, bold: true, color: C.cyan });
  const guards = [
    "封闭航段、显式 blocked edge",
    "流量已达容量上限",
    "穿过建筑、城市边界或低于地面",
    "与激活三维管制区相交（含边界接触）",
    "水平投影穿越雷暴区",
  ];
  guards.forEach((item, i) => {
    const y = 236 + i * 56;
    rect(slide, 74, y + 17, 9, 9, i === 4 ? C.red : C.cyan);
    text(slide, item, 99, y, 605, 42, { size: 22, color: C.white });
  });
  rect(slide, 746, 175, 1, 322, C.rule);
  text(slide, "可采纳的 A* 启发值", 794, 174, 414, 43, { size: 27, bold: true, color: C.cyan });
  text(slide, "h(n) = w_d × d₃ᴅ(n, goal) / 1000", 794, 239, 414, 59, { size: 24, bold: true });
  text(slide, "每条边的距离不短于端点直线距离，其余代价非负，因此 h 不会高估剩余成本。", 794, 314, 400, 104, { size: 21, color: C.muted, valign: "top" });
  text(slide, "最优性范围", 794, 429, 160, 36, { size: 22, bold: true, color: C.amber });
  text(slide, "当前快照中通过硬约束的图及加权目标；不代表连续空间全局最优。", 794, 468, 406, 75, { size: 20, color: C.muted, valign: "top" });
  rule(slide, 72, 561, 1136, C.rule, 1);
  text(slide, "航程超限时：同一可行图上回退到最短距离 Dijkstra，并标注该结果不保证航程约束下的加权最优。", 72, 584, 1136, 62, { size: 21, color: C.white });
  notes(slide, "硬约束、3D 管制区、雷暴保守阻断、可采纳启发值证明和 max_distance_m 回退范围见 docs/path-planning.md 及 algorithms/path_planning/astar.py。w_distance 为 0 时启发值为 0，算法退化为 Dijkstra。航程约束下的多标签资源约束最短路尚未实现。");
}

// 6. Continuous conflict detection
{
  const slide = addSlide();
  header(slide, "连续时空冲突检测：判断间隔何时首次失守");
  text(slide, "默认预测窗 10 s  ·  水平间隔 30 m  ·  垂直间隔 15 m", 72, 158, 1136, 42, { size: 23, bold: true, color: C.amber, align: "center" });
  const steps = [
    ["01  粗筛候选", "用整段轨迹的扫掠包围盒\n快速排除不可能相遇的飞机对"],
    ["02  对齐时间", "仅在两条分段线性轨迹\n共同覆盖的时间段内插值"],
    ["03  求首次进入", "解水平距离二次不等式\n与垂直距离线性区间"],
  ];
  const xs = [72, 463, 854];
  steps.forEach(([label, body], i) => {
    text(slide, label, xs[i], 248, 320, 54, { size: 25, bold: true, color: C.cyan });
    text(slide, body, xs[i], 316, 328, 96, { size: 22, color: C.muted, valign: "top" });
    if (i < 2) text(slide, "→", xs[i] + 337, 267, 46, 42, { size: 30, color: C.dim, align: "center" });
  });
  rule(slide, 72, 444, 1136, C.rule, 1);
  text(slide, "只有在同一绝对时刻满足水平距离 ≤ 30 m 且垂直距离 ≤ 15 m，才报告预测冲突", 95, 475, 1090, 76, { size: 25, bold: true, align: "center" });
  text(slide, "先取交叠区间，再求区间交集：避免只在离散仿真步采样而漏掉步间相遇", 95, 572, 1090, 52, { size: 21, color: C.muted, align: "center" });
  notes(slide, "实现位于 algorithms/conflict_detection/continuous.py，阈值默认值见 algorithms/conflict_detection/models.py。算法先用每架机整段轨迹的保守扫掠包围盒做 broad phase，然后遍历时间重叠的轨迹段，在同步时间域中求水平距离二次不等式和垂直距离区间的交集，返回首次进入保护间隔的时间。飞机对的最坏枚举仍为 O(N²)；包围盒只减少精确计算量。");
}

// 7. Conflict resolution
{
  const slide = addSlide();
  header(slide, "规则解脱：候选动作必须通过全机安全复检");
  text(slide, "候选动作", 72, 174, 160, 42, { size: 24, bold: true, color: C.muted });
  const actions = ["调速", "调高", "改航", "延迟"];
  actions.forEach((a, i) => {
    const x = 240 + i * 224;
    text(slide, a, x, 169, 174, 50, { size: 26, bold: true, color: i === 2 ? C.cyan : C.white, align: "center" });
    if (i < actions.length - 1) text(slide, "·", x + 176, 172, 40, 42, { size: 28, color: C.dim, align: "center" });
  });
  rule(slide, 72, 238, 1136, C.rule, 1);
  const stages = [
    ["轨迹连续", "从决策时刻的\n实际位置衔接"],
    ["硬约束过滤", "剔除不可行或\n未覆盖预测窗候选"],
    ["全机复检", "只替换一架轨迹，\n与其余飞机逐一检测"],
    ["代价排序", "在安全候选中\n选择代价最低动作"],
  ];
  const stageX = [72, 359, 646, 933];
  stages.forEach(([titleText, body], i) => {
    text(slide, titleText, stageX[i], 284, 242, 48, { size: 24, bold: true, color: C.cyan });
    text(slide, body, stageX[i], 344, 242, 84, { size: 21, color: C.muted, valign: "top" });
    if (i < 3) text(slide, "→", stageX[i] + 247, 294, 32, 36, { size: 25, color: C.dim, align: "center" });
  });
  text(slide, "J_res = w_delay·Δt + w_energy·ΔE + w_congestion·ΔC", 94, 472, 1092, 58, { size: 27, bold: true, align: "center" });
  rule(slide, 72, 553, 1136, C.rule, 1);
  text(slide, "没有安全候选 → 标记 unresolved 并暂停，绝不为了继续仿真接受冲突", 82, 577, 1116, 54, { size: 23, bold: true, color: C.amber, align: "center" });
  notes(slide, "实现见 algorithms/conflict_resolution/rules.py 与 models.py。仿真器生成并先验证候选；resolver 独立确认时间连续性与预测窗完整性，然后把变更轨迹分别与其它每架飞机检测冲突，复杂度为 O(N) 每候选。安全是硬约束，延误、额外能耗与拥堵只用于对安全候选排序。无解返回 unresolved；引擎对无法安全解脱的情形暂停。");
}

// 8. Dynamic events and emergency diversion
{
  const slide = addSlide();
  header(slide, "扰动处置：先保证安全撤离，再继续任务规划");
  text(slide, "新天气或临时管制覆盖在飞无人机", 72, 174, 520, 54, { size: 25, bold: true, color: C.cyan });
  text(slide, "1  从实际位置寻找区域外出口\n\n2  校验建筑碰撞、其他管制区与雷暴\n\n3  连续离开禁区并禁止重新进入\n\n4  到达安全出口后，再规划剩余任务", 72, 246, 530, 286, { size: 22, color: C.white, valign: "top" });
  text(slide, "无安全出口时告警并暂停该机", 72, 557, 530, 44, { size: 20, bold: true, color: C.amber });
  rect(slide, 636, 174, 1, 424, C.rule);
  text(slide, "故障备降", 688, 174, 450, 54, { size: 25, bold: true, color: C.cyan });
  text(slide, "可用航程 = 电量 × 最大航程 × 0.55", 688, 247, 455, 44, { size: 23, bold: true });
  text(slide, "先筛掉不可达或无容量的备降点，再按可行路径距离选择最近目标并预留机位。", 688, 308, 448, 115, { size: 21, color: C.muted, valign: "top" });
  rule(slide, 688, 447, 456, C.rule, 1);
  text(slide, "固定种子实测案例", 688, 468, 450, 38, { size: 20, color: C.muted });
  text(slide, "70 s 故障注入  ·  EB-8  ·  171 m 规划距离", 688, 511, 470, 55, { size: 22, bold: true });
  text(slide, "报告记录最终真实抵达备降点", 688, 572, 455, 34, { size: 20, color: C.amber });
  notes(slide, "天气和空域覆盖撤离逻辑见 simulation/engine/planning.py；备降选点和机位预留见 algorithms/emergency/diversion.py。available_range 乘以 range_derating=0.55，剩余航程内筛选可达且未满载的备降点。案例数据来自 data/demo_report.json：70 秒故障事件选择 EB-8，规划距离 171.17 米；该 100 机报告最终记录 1 个真实备降抵达。");
}

// 9. Measured demo results
{
  const slide = addSlide();
  header(slide, "固定种子仿真：100 架机在动态事件中持续运行");
  text(slide, "seed = 42  ·  459 s 仿真  ·  779 条航路", 72, 149, 1136, 38, { size: 20, color: C.muted });
  const metrics = [
    ["99 / 100", "到达原任务目的地"],
    ["1 架", "真实备降并抵达"],
    ["30 次", "冲突规则解脱"],
    ["0", "最终剩余冲突"],
  ];
  metrics.forEach(([value, label], i) => {
    const x = 72 + (i % 2) * 253;
    const y = 220 + Math.floor(i / 2) * 166;
    text(slide, value, x, y, 224, 66, { size: 42, bold: true, color: i === 3 ? C.cyan : C.white });
    text(slide, label, x, y + 75, 224, 42, { size: 21, color: C.muted });
  });
  text(slide, "事件处理计数（架 / 次）", 604, 192, 580, 40, { size: 22, bold: true });
  const chart = slide.charts.add("bar", {
    position: { left: 592, top: 234, width: 608, height: 372 },
    categories: ["拥堵改航（架）", "雷暴改航（架）", "冲突解脱（次）"],
    series: [{ name: "实际处理量", values: [4, 20, 30], fill: C.cyan }],
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 64 },
    hasLegend: false,
    chartFill: { color: C.bg, transparency: 100000 },
    plotAreaFill: { color: C.bg, transparency: 100000 },
    chartLine: { style: "solid", fill: "none", width: 0 },
    plotAreaLine: { style: "solid", fill: "none", width: 0 },
    xAxis: { min: 0, max: 35, majorUnit: 10, textStyle: { typeface: fontFamily, fontSize: 16, fill: C.muted }, majorGridlines: { style: "solid", fill: C.rule, width: 1 }, line: { style: "solid", fill: C.rule, width: 1 } },
    yAxis: { textStyle: { typeface: fontFamily, fontSize: 18, fill: C.white }, majorGridlines: null, line: { style: "solid", fill: "none", width: 0 } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { typeface: fontFamily, fontSize: 18, fill: C.white, bold: true } },
  });
  notes(slide, "报告字段来自 data/demo_report.json，口径解释见 docs/demo.md。99 是到达原目的地的任务数；1 是真实备降，最终任务状态计为 diverted；30 是解脱次数；最终剩余预测/已检测冲突均为 0。容量缩减影响并改航 4 架，雷暴事件影响并改航 20 架。图中事件处理量不同类别分别按架数与解脱次数统计，不作为同一效率指标比较。结果依赖 seed、参数、机器与停止时刻，不是预设得分。");
}

// 10. Positioning, limits, next steps
{
  const slide = addSlide();
  header(slide, "方案定位：可解释的安全闭环，清楚标注工程边界");
  const pillars = [
    ["路线规划", "五项加权 A*\n精确硬约束\n返回代价分解"],
    ["冲突管理", "连续轨迹检测\n候选动作比较\n全机安全复检"],
    ["动态响应", "事件触发重规划\n危险区先撤离\n故障机真实备降"],
  ];
  pillars.forEach(([titleText, body], i) => {
    const x = 72 + i * 390;
    text(slide, titleText, x, 178, 336, 43, { size: 25, bold: true, color: C.cyan });
    text(slide, body, x, 237, 336, 126, { size: 22, color: C.white, valign: "top" });
    if (i < 2) rect(slide, x + 354, 181, 1, 180, C.rule);
  });
  rule(slide, 72, 397, 1136, C.rule, 1);
  text(slide, "当前模型边界", 72, 423, 250, 41, { size: 24, bold: true, color: C.amber });
  text(slide, "能耗为几何代理；冲突候选对枚举为 O(N²)；航程约束下多标签最优搜索与已训练 GNN / 强化学习模型尚未实现。", 72, 476, 1136, 65, { size: 21, color: C.muted });
  text(slide, "后续可替换方向：空间索引、物理能耗模型、资源约束路径搜索；保持统一输入输出接口。", 72, 570, 1136, 62, { size: 22, bold: true, color: C.white });
  notes(slide, "项目声明的边界和未来方向见 README.md 与 docs/path-planning.md。当前路径规划器、冲突检测器均定义可替换协议；但 GNN、PPO/MAPPO 等只属于后续可能方向，并未训练或在本项目中使用。成对冲突检测目前依靠保守包围盒降低精确运算量，候选飞机对枚举仍为 O(N²)。");
}

await fs.mkdir(path.dirname(finalPath), { recursive: true });
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

for (let i = 0; i < presentation.slides.items.length; i++) {
  const slide = presentation.slides.items[i];
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(buildDir, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(buildDir, `slide-${String(i + 1).padStart(2, "0")}.layout.json`), await layout.text());
}
const montage = await presentation.export({ format: "png", montage: true, scale: 0.5 });
await fs.writeFile(path.join(buildDir, "montage.png"), new Uint8Array(await montage.arrayBuffer()));

const result = await finalizePresentation({
  requiredNativeChartOwnerSlides: [9],
  requiredNativeTableOwnerSlides: [],
  materializeLiteralChartWorkbooks: true,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: "C:/Users/18980/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: [fontFamily] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "天枢智航_算法设计答辩.validation.json"),
});
console.log(JSON.stringify({ slideCount: presentation.slides.items.length, finalPath, result }));
