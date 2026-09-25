from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "答辩交付"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "中国民用航空飞行学院+微笑^^调查队"
REPORT = json.loads((ROOT / "data/demo_report.json").read_text(encoding="utf-8"))
SCENARIOS = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "data/scenarios").glob("*.json")}

pdfmetrics.registerFont(TTFont("YaHei", r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("YaHei-Bold", r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))
pdfmetrics.registerFontFamily("YaHei", normal="YaHei", bold="YaHei-Bold")

NAVY = colors.HexColor("#12303D")
TEAL = colors.HexColor("#137E7A")
INK = colors.HexColor("#182B34")
MUTED = colors.HexColor("#536B76")
PALE = colors.HexColor("#EDF5F5")
LINE = colors.HexColor("#D8E2E5")

styles = {
    "title": ParagraphStyle("title", fontName="YaHei-Bold", fontSize=24, leading=34, textColor=INK, spaceAfter=15),
    "subtitle": ParagraphStyle("subtitle", fontName="YaHei", fontSize=12, leading=19, textColor=MUTED, spaceAfter=11),
    "h1": ParagraphStyle("h1", fontName="YaHei-Bold", fontSize=16, leading=23, textColor=INK, spaceBefore=17, spaceAfter=9, keepWithNext=True),
    "h2": ParagraphStyle("h2", fontName="YaHei-Bold", fontSize=11.5, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=6, keepWithNext=True),
    "body": ParagraphStyle("body", fontName="YaHei", fontSize=9.5, leading=16, textColor=INK, spaceAfter=8, wordWrap="CJK"),
    "small": ParagraphStyle("small", fontName="YaHei", fontSize=8.3, leading=13, textColor=MUTED, spaceAfter=6, wordWrap="CJK"),
    "table": ParagraphStyle("table", fontName="YaHei", fontSize=8.3, leading=12.5, textColor=INK, wordWrap="CJK"),
    "tablehead": ParagraphStyle("tablehead", fontName="YaHei-Bold", fontSize=8.3, leading=12.5, textColor=colors.white, wordWrap="CJK"),
    "center": ParagraphStyle("center", fontName="YaHei", fontSize=9, leading=15, textColor=MUTED, alignment=TA_CENTER),
}

def P(text, kind="body"):
    return Paragraph(text, styles[kind])

def heading(text, level=1):
    return P(text, "h1" if level == 1 else "h2")

def body(text):
    return P(text)

def bullet(text):
    return P("•  " + text)

def table(headers, rows, widths):
    data = [[P(str(x), "tablehead") for x in headers]]
    data += [[P(str(x), "table") for x in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), .45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t

def page_canvas(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(LINE)
    canvas.line(18*mm, 18*mm, w-18*mm, 18*mm)
    canvas.setFont("YaHei", 7.3)
    canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 13*mm, "中国民用航空飞行学院 · 微笑^^调查队 · 天枢智航")
    canvas.drawRightString(w-18*mm, 13*mm, f"{doc.page}")
    canvas.restoreState()

def save(name, story):
    path = OUT / f"{PREFIX}_{name}.pdf"
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
                      topMargin=19*mm, bottomMargin=24*mm, title=name,
                      author="中国民用航空飞行学院 微笑^^调查队").build(story, onFirstPage=page_canvas, onLaterPages=page_canvas)
    print(path)
    return path

metrics = REPORT["metrics"]
events = REPORT["events"]
congestion = next(e for e in events if e["type"] == "event_route_congestion")
weather = next(e for e in events if e["type"] == "event_weather")
failure = next(e for e in events if e["type"] == "event_aircraft_failure")
landing = next(e for e in events if e["type"] == "event_emergency_landing")

proposal = [
    Spacer(1, 23*mm),
    P("城市空中交通规划创新方案", "title"),
    P("天枢智航：城市低空交通智能规划与自主协同系统", "subtitle"),
    HRFlowable(width="100%", thickness=1.2, color=TEAL),
    Spacer(1, 15*mm),
    table(["参赛单位", "参赛队伍", "答辩人"], [["中国民用航空飞行学院", "微笑^^调查队", "陈奕冰"]], [55*mm, 55*mm, 45*mm]),
    Spacer(1, 12*mm),
    heading("方案摘要"),
    body("本方案面向城市低空航路网规划与多机运行管理，构建一套可离线运行的仿真平台。系统使用分层有向航路网和五项加权 A* 选择安全可行路径；在天气、管制、拥堵和故障扰动下重规划；以连续时空轨迹预测、规则候选和全机复检处理潜在冲突；最后将实际运动、事件和指标同步到三维控制台。"),
    body("固定种子 42 的 100 机完整演示在 459 个仿真秒结束：99 项任务到达原目的地，1 架故障机实际抵达备降点，记录 30 次规则解脱，最终剩余冲突为 0。该结果来自仓库 data/demo_report.json 的单次可复现实测，不能视为真实运行安全认证或跨场景性能保证。"),
    heading("参赛任务对应"),
    table(["评审关注", "本作品可展示的证据"], [
        ["科学性与技术难度", "硬约束筛边、可解释代价、可采纳启发值；连续轨迹冲突判定与规则解脱"],
        ["方案完整度与落地性", "三维城市、航路网、仿真执行、HTTP/WebSocket、控制台、报告与可复现工程"],
        ["附加任务", "航路规划、动态流量、冲突解脱、天气与管制、故障备降、可视化统计已覆盖；地面车辆协同和赛事指定仿真系统接口尚未接入"],
    ], [43*mm, 112*mm]),
    PageBreak(),
    heading("一 项目目标与场景"),
    body("城市低空运行需要同时回答三类问题：哪些航段在建筑、边界、空域和气象条件下可飞；在安全可行域内怎样平衡距离、风险、拥堵和能耗；多机接近时如何提前检测并选择连续、可执行的避让动作。平台将这三类问题放在同一状态闭环中，而不是只输出一次静态路线。"),
    heading("系统边界", 2),
    bullet("运行对象为程序化生成的仿真城区和无人机任务，空间坐标使用局部 ENU 米制；不存在真实城市测绘数据或真实飞行指挥链路。"),
    bullet("现场可演示 100 机综合场景，以及拥堵、雷暴、临时管制、故障备降、两机冲突五个 24 机独立场景。"),
    bullet("系统尚未对接赛事指定的低空运行仿真平台，也未实现空地车机联合调度；如主办方提供接口规范，可通过现有实体与事件适配层接入。"),
    heading("二 技术架构"),
    table(["层次", "模块", "职责与交付"], [
        ["交互层", "Vue 3、Cesium、ECharts", "三维场景、控制命令、单机场景、运行指标和事件留痕"],
        ["服务层", "FastAPI、WebSocket", "命令校验、环境版本、实时快照、报告导出"],
        ["仿真层", "固定步长引擎、事件调度", "任务推进、容量占用、天气与管制注入、检查点"],
        ["算法层", "规划、检测、解脱、备降", "路径搜索、连续预测、安全候选选择和应急处置"],
        ["数据层", "领域模型、SQLite", "实体约束、事务保存、复现实验"],
    ], [22*mm, 48*mm, 85*mm]),
    body("依赖方向为 backend → simulation → algorithms → core。算法读取一致快照，不从前端状态直接决定安全动作；环境变化触发新规划，仿真每步复核预测与实际运动。"),
    heading("三 关键算法与可解释性"),
    heading("3.1 分层航路网与硬约束", 2),
    body("航路图包含高度层、航点、起降点和备降点。规划前剔除封闭或超容量航段、穿越建筑与城市边界的航段、与激活管制区三维棱柱相交的航段，以及水平投影穿越雷暴区的航段。起终点也执行安全校验。"),
    heading("3.2 五项加权 A*", 2),
    body("每条边的代价为 J(e)=w<sub>d</sub>L+w<sub>r</sub>Lr+w<sub>c</sub>Lu+w<sub>e</sub>(L+4H)+w<sub>w</sub>Lp<sub>w</sub>。L 为三维航段千米长度，r 为风险等级，u 为流量与容量之比，H 为上升高度千米数，p<sub>w</sub> 为气象暴露惩罚。默认权重依次为 1、2、1.5、0.8、3，均为非负数。"),
    body("启发值为距离权重乘以至终点的三维直线距离；边长不短于端点直线距离，其他分项非负，因此在当前快照的可行图上不会高估剩余代价。返回路线时同时提供五项代价分解。航程约束触发的最短距离回退会显式标识，不宣称其为航程约束下的加权最优解。"),
    heading("3.3 连续冲突预测与规则解脱", 2),
    body("默认 10 秒预测窗内，系统先用扫掠包围盒排除不可能相遇的机对，再在两条分段线性轨迹共同覆盖的时间区间求水平距离和垂直距离阈值的交集。只有同一时刻水平间隔不大于 30 米且垂直间隔不大于 15 米，才报告预测冲突。"),
    body("候选动作包括调速、调高、改航和延迟。每个候选须从飞机实际位置连续衔接，并通过建筑、禁入区、剩余航程与全机间距复检。无安全候选或临近冲突未解时，仿真暂停并留痕。"),
    heading("四 动态扰动与应急处置"),
    table(["事件", "处置逻辑", "可核查输出"], [
        ["航路拥堵", "收缩容量，更新占用，受影响任务改航或等待", "受影响机号、改航机号、容量变化"],
        ["雷暴天气", "在区内的飞行器先从实际位置撤离，再规划剩余航路；未进入者绕行", "撤离、改航和等待清单"],
        ["临时管制", "三维禁入区更新，同样执行先撤离后绕行", "禁区版本与处置记录"],
        ["飞行器故障", "按电量修正可飞距离，筛选可达且有容量的备降点，实际推进降落", "备降点、规划距离、真实到达事件"],
        ["预测冲突", "生成规则候选，检查全机安全后选最小代价动作", "冲突时刻、机对、动作与剩余冲突"],
    ], [25*mm, 79*mm, 51*mm]),
    body("该流程强调物理连续性：禁入区覆盖已在飞的飞机时，不能仅让后续 A* 从禁区外航点重新起算；故障机也不能只在面板上显示“已备降”，必须在运动记录中到达备降点。"),
    heading("五 仿真验证"),
    heading("5.1 100 机完整场景", 2),
    table(["指标", "实测值", "口径"], [
        ["任务完成", f"{metrics['completed_missions']} / 100", "抵达原目的地；另 1 架抵达备降点"],
        ["规则解脱", str(metrics["resolved_conflicts"]), "事件日志累计；结束时剩余冲突 0"],
        ["累计飞行", f"{metrics['total_flight_distance_m']/1000:.2f} km", "实际推进航段的三维长度合计"],
        ["平均延误", f"{metrics['average_delay_s']:.2f} s", "仿真时间相对初始计划时长"],
        ["执行耗时", f"{REPORT['benchmark']['execution_seconds']:.1f} s", "本机无浏览器 459 步墙钟时间"],
    ], [35*mm, 31*mm, 89*mm]),
    body(f"20 秒拥堵影响 {len(congestion['result']['affected_aircraft'])} 架并全部改航；45 秒雷暴影响 {len(weather['result']['affected_aircraft'])} 架并全部改航，其中 {len(weather['result']['evacuating_aircraft'])} 架从雷暴区域内撤离。70 秒故障机选择 {failure['result']['bay_id']}，规划距离 {failure['result']['planned_distance_m']:.0f} 米，后续日志记录真实到达事件。"),
    heading("5.2 五个独立场景", 2),
    table(["场景", "固定种子结果", "报告"], [
        ["拥堵", "4 架受影响，4 架改航", "congestion.json"],
        ["雷暴", "8 架受影响，8 架改航，2 架区内撤离", "weather.json"],
        ["管制", "8 架受影响，8 架改航，2 架区内撤离", "closure.json"],
        ["故障", "EB-0 备降，记录真实到达", "failure.json"],
        ["冲突", "检测并完成 1 次规则解脱", "conflict.json"],
    ], [22*mm, 89*mm, 44*mm]),
    body("五个场景均为 seed=42 的单次回放。可通过 scripts/run_demo_headless.py 重新生成报告，并核对事件结果和运行指标；不同种子、硬件与参数可能产生不同结果。"),
    heading("六 工程落地与合规路径"),
    body("现阶段平台适合竞赛演示、算法对照和仿真复核。它使用 Python 3.12、FastAPI、SQLite 与 Vue 3，可离线生成程序化城市，不依赖商业地图服务。单个服务实例持有唯一仿真状态，SQLite 保存检查点；生产部署前需重新设计多实例场景所有权、稳定数据接口和运维监控。"),
    body("真实空域应用应将城市地理数据、经核验的空域与气象数据、航空器性能及运行许可接入，并由有权主体按适用规定完成空域申请、运行管理和异常处置。算法输出只能作为规划辅助，不能代替许可、现场态势感知或飞控安全论证。相关法规见文末中国民航局公开文本。"),
    heading("七 创新点与局限"),
    table(["已实现的创新组合", "尚待完善"], [
        ["五项代价可解释 A* 与硬约束同图搜索；环境版本变化即重规划", "航程约束下的多标签全局加权最优搜索未实现"],
        ["连续时空冲突检测和从实际位置衔接的规则候选", "机对筛选仍以 O(N²) 枚举为基础，需要空间索引"],
        ["雷暴和管制区域内先撤离再改航，故障机真实到达备降点", "能耗与天气为工程代理模型，未校准真实机型"],
        ["算法、服务、仿真、三维展示和报告形成可复现闭环", "无已训练 AI 决策器；地面车辆协同与赛事指定平台适配未完成"],
    ], [77.5*mm, 77.5*mm]),
    heading("八 团队自主贡献与原创性确认"),
    body("提交工程包含航路规划、冲突检测与解脱、事件仿真、服务接口、三维控制台、自动演示脚本、单元与集成测试。源码与数据报告随附加任务工程包提供，评委可按参数说明复现。参赛产品由团队独立设计、开发且不存在知识产权纠纷的正式承诺，应由队伍负责人在提交前核对并签署；本文件不代替该签署。"),
    Spacer(1, 5*mm),
    P("负责人确认：____________________    日期：____________________", "small"),
    heading("现场系统画面"),
    Image(str(ROOT / "output/答辩控制台总览.png"), width=150*mm, height=114.6*mm),
    P("图 1  本地程序化城市与仿真控制台；所示为独立故障备降场景，并非真实空域态势。", "small"),
    heading("现场操作与证据核对", 2),
    table(["操作", "评委可见证据"], [
        ["选择单项雷暴或管制场景", "地图跟踪受影响飞行器，事件记录列出撤离与改航机号"],
        ["启动故障备降场景", "飞行器状态与位置变化，事件记录出现实际到达备降点"],
        ["打开 100 机报告", "核对任务终态、30 次规则解脱、0 个最终剩余冲突和完整历史"],
    ], [55*mm, 100*mm]),
    heading("参考与证据"),
    P("[1] 仓库 docs/architecture.md、docs/path-planning.md、docs/demo.md、README.md；数据 data/demo_report.json 与 data/scenarios/*.json。", "small"),
    P('<link href="https://www.caac.gov.cn/XXGK/XXGK/FLFG/202401/t20240115_222642.html">[2] 中国民航局《无人驾驶航空器飞行管理暂行条例》</link>。', "small"),
    P('<link href="https://app.caac.gov.cn/XXGK/XXGK/MHGZ/202401/t20240103_222566.html">[3] 中国民航局《民用无人驾驶航空器运行安全管理规则》</link>。', "small"),
]
save("城市空中交通规划创新方案", proposal)

params = [
    P("仿真工程参数说明", "title"),
    P("天枢智航 | 固定种子 42 的可复现演示", "subtitle"),
    heading("一 环境与运行"),
    table(["项目", "配置 / 命令", "说明"], [
        ["运行环境", "Windows PowerShell、Python 3.12+、uv、Node.js 22.12+", "依赖版本由 uv.lock 与 frontend/package-lock.json 锁定"],
        ["安装", ".\\scripts\\setup.ps1", "在工程根目录执行"],
        ["一键演示", ".\\scripts\\run_demo.ps1", "后端默认 8011；前端默认 5173"],
        ["无浏览器报告", ".venv-runtime\\Scripts\\python.exe -X utf8 scripts\\run_demo_headless.py --aircraft 100 --steps 600 --seed 42", "输出 data/demo_report.json"],
        ["单项场景", "--scenario congestion|weather|closure|failure|conflict --steps 180", "默认每项 24 架，输出 data/scenarios/"],
    ], [31*mm, 81*mm, 43*mm]),
    body("工程使用程序化仿真城市，坐标为局部 ENU 米制，x 向东、y 向北、z 为离地高度。仿真秒与真实墙钟秒分别记录；10× 为目标倍率，不保证在所有计算机上达到实际 10×。"),
    heading("二 服务与算法配置"),
    body("下表均可使用 TS_ 前缀环境变量或 .env 覆盖；默认值来自 backend/config/settings.py。权重必须为有限非负数。"),
    table(["环境变量", "默认值", "含义"], [
        ["TS_HOST / TS_PORT", "127.0.0.1 / 8011", "后端监听地址与端口"],
        ["TS_DATABASE_PATH", "data/tianshu.sqlite3", "SQLite 检查点路径"],
        ["TS_SIMULATION_DEFAULT_SPEED", "10", "目标仿真倍率"],
        ["TS_SIMULATION_TICK_SECONDS", "1 s", "单步仿真时间"],
        ["TS_COST_WEIGHT_DISTANCE", "1", "距离分项权重"],
        ["TS_COST_WEIGHT_RISK", "2", "风险分项权重"],
        ["TS_COST_WEIGHT_CONGESTION", "1.5", "拥堵分项权重"],
        ["TS_COST_WEIGHT_ENERGY", "0.8", "能耗代理权重"],
        ["TS_COST_WEIGHT_WEATHER", "3", "气象分项权重"],
        ["TS_CONFLICT_HORIZONTAL_SEPARATION_M", "30 m", "水平预测间隔阈值"],
        ["TS_CONFLICT_VERTICAL_SEPARATION_M", "15 m", "垂直预测间隔阈值"],
        ["TS_CONFLICT_TIME_WINDOW_S", "10 s", "未来轨迹预测窗"],
        ["TS_CONFLICT_ALTITUDE_STEP_M", "30 m", "调高候选的高度步长"],
        ["TS_CONFLICT_MAX_VERTICAL_SPEED_MPS", "2 m/s", "调高候选的最大垂直速度"],
    ], [66*mm, 31*mm, 58*mm]),
    heading("三 算法参数解释"),
    body("规划代价 J(e)=w<sub>d</sub>L+w<sub>r</sub>Lr+w<sub>c</sub>Lu+w<sub>e</sub>(L+4H)+w<sub>w</sub>Lp<sub>w</sub>。距离与爬升以千米计；“4”是爬升能耗代理系数，不等于实际瓦时。航路容量、建筑、地面、城市边界、雷暴与临时管制均可作为硬约束。"),
    body("冲突判定为同一绝对时刻水平距离 ≤30 米且垂直距离 ≤15 米。候选解脱动作包括调速、调高、改航、延迟，按延误、额外能耗代理及拥堵增量的非负权重排序。无安全方案则暂停仿真。"),
    heading("四 事件时序与预设"),
    table(["模式", "事件时刻", "停止或验收条件"], [
        ["full（100 机）", "20 s 拥堵；45 s 雷暴；70 s 故障；95 s 交汇意图；160 s 天气解除", "全部任务终态或 600 s 上限；220 s 仅表示扰动阶段结束"],
        ["congestion", "10 s", "观察受影响飞行器改航；注入后 55 s 停止"],
        ["weather / closure", "25 s", "观察区内撤离与绕行；注入后 55 s 停止"],
        ["failure", "40 s", "故障机到达备降点后继续记录至少 12 s"],
        ["conflict", "40 s", "真实规则解脱后继续记录至少 12 s"],
    ], [38*mm, 66*mm, 51*mm]),
    heading("五 指标口径"),
    table(["字段", "解释"], [
        ["completed_missions", "到达原任务目的地的数量；备降单独记录，不计入该值"],
        ["total_flight_distance_m", "所有飞行器实际推进航段的三维长度之和"],
        ["average_delay_s", "按仿真时间相对初始计划时长计算；未结束任务使用预计剩余时间"],
        ["route_utilization", "当前航段占用总和除以容量总和；全部降落后可为 0"],
        ["resolved_conflicts", "累计成功执行的规则解脱次数"],
        ["emergency_response_ms", "故障注入到备降决策记录的墙钟耗时，不含飞行至备降点时间"],
    ], [53*mm, 102*mm]),
    heading("六 工程文件与安全边界"),
    body("仿真工程包包含算法、仿真、后端、前端、测试、脚本、锁文件、设计文档、固定种子报告和参数示例。源代码压缩包另行加密。源码包不含 .venv、node_modules、SQLite 运行库、.env 或真实空域数据。"),
    table(["核对文件", "用途"], [
        ["data/demo_report.json", "100 机完整场景的指标、事件与历史采样"],
        ["data/scenarios/*.json", "五个 24 机独立事件场景的结果"],
        ["docs/demo.md", "事件时序、指标口径与运行边界"],
        ["backend/config/settings.py", "可覆盖的服务、代价与安全阈值默认值"],
    ], [53*mm, 102*mm]),
    Spacer(1, 5*mm),
    body("该平台是竞赛仿真，不支持真实航空器控制。地面车辆协同调度与赛事指定仿真系统格式目前没有接入；参赛现场如要求专用工程格式，应先获取官方接口/模板并转换。"),
]
save("仿真参数说明", params)

notes = [
    P("现场讲稿与专家问答", "title"),
    P("5 分钟讲解参考稿 | 答辩人 陈奕冰", "subtitle"),
    heading("讲解节奏"),
    table(["页码", "时间", "讲解重点"], [
        ["1", "0:00-0:15", "项目名称、目标和可演示系统"],
        ["2", "0:15-0:45", "可飞、效率、多机安全三个问题"],
        ["3", "0:45-1:20", "从环境快照到控制台的闭环"],
        ["4", "1:20-2:10", "五项加权 A*、硬约束与可解释代价"],
        ["5", "2:10-2:55", "连续冲突预测、全机复检与安全暂停"],
        ["6", "2:55-3:55", "现场演示：单项事件与三维控制台"],
        ["7", "3:55-4:35", "固定种子 100 机实测结果"],
        ["8", "4:35-5:00", "工程边界、落地路径和总结"],
    ], [17*mm, 31*mm, 107*mm]),
    heading("逐页讲稿"),
    body("第 1 页：各位评委好，我是陈奕冰，来自中国民用航空飞行学院微笑^^调查队。我们的作品是天枢智航，一套城市低空交通规划与自主协同仿真系统。今天展示系统怎样在动态扰动中规划航路、保障间隔，并留下可核查的运行记录。"),
    body("第 2 页：城市低空规划不能只找一条最短路。建筑、临时管制和雷暴决定能否飞行，容量和任务压力影响效率，多架飞行器还可能在未来几秒相遇。我们把可行性、路线代价和冲突处置放在同一运行闭环。"),
    body("第 3 页：系统从三维城市与任务读取一致快照，先过滤不可飞航段，再规划航路；仿真引擎逐步推进飞机，并在事件注入后重规划。服务端把状态通过 WebSocket 发送到 Cesium 控制台，所有图表与事件结果都来自仿真快照。"),
    body("第 4 页：规划器使用五项加权 A*，分别计入距离、风险、拥堵、爬升能耗代理和气象。建筑碰撞、雷暴和管制属于硬约束，不能靠低权重绕过。启发值只使用三维直线距离的距离项，在当前可行图上不会高估剩余代价；结果还返回每项代价，便于解释为什么绕行。"),
    body("第 5 页：冲突模块在默认 10 秒预测窗内计算连续轨迹，不只看离散仿真帧。只有同一时刻水平 30 米、垂直 15 米间隔都不足才判冲突。随后生成调速、调高、改航、延迟候选，从实际位置连续衔接，并逐一对全机复检；没有安全解时暂停运行。"),
    body("第 6 页：现场先展示一个单项事件。比如雷暴或临时管制覆盖在飞飞机时，系统会先让区内飞机撤离，再沿新的可行航路继续任务；故障场景会把飞机真正推进至备降点。右侧可查看实时指标，底部可展开事件处置与原始结果。切换场景会重置当前状态，因此演示前先导出重要报告。"),
    body("第 7 页：固定种子 42 的 100 机完整场景，运行到 459 个仿真秒自动结束。99 项任务抵达原目的地，1 架故障机实际备降；记录 30 次规则解脱，最后剩余冲突为 0。累计飞行 305.09 公里。这里展示的是一次可复现实测，不把它等同于真实运行认证。"),
    body("第 8 页：目前我们已经交付可运行的算法、仿真、服务、控制台与报告。能耗和天气仍是代理模型，地面车辆协同和赛事指定平台接口也还需补齐。下一步应接入经核验的空域、气象和机型数据，在许可与安全论证框架下做试点验证。谢谢各位评委。"),
    heading("常见问题与简答"),
    table(["评委可能提问", "建议回答"], [
        ["你们用了 AI 吗？", "当前核心是可解释的加权 A* 与规则策略，没有训练 GNN 或强化学习模型。我们不把传统算法包装成已落地的 AI。"],
        ["为什么 A* 最优？", "只在当前硬约束过滤后的快照图和所定义加权代价上成立；启发值由距离下界构造。航程回退只保证可行，不保证约束下加权最优。"],
        ["30 米/15 米是法规标准吗？", "不是。它们是本仿真默认的可配置安全阈值。真实运行须按机型、空域、任务与适用规则另行确定。"],
        ["冲突如何避免漏检？", "对同一时间区间内的分段线性轨迹求水平与垂直阈值交集，能发现仿真步之间的相遇；运动后还会复检实际轨迹。"],
        ["安全候选都失败怎么办？", "记录未解冲突并暂停仿真，不为了保持演示连续而接受临近碰撞。"],
        ["结果能否复现？", "固定 seed=42、参数和脚本可重跑；报告包含事件与历史。不同硬件会改变墙钟耗时，改变种子可能改变任务结果。"],
        ["为何 99/100 不是 100？", "1 架在故障后执行应急备降，未到原目的地，因此不计完成任务；报告单独记录真实到达备降点。"],
        ["附加任务是否全部完成？", "已覆盖航路、流量、冲突、动态事件和看板；地面车辆协同和赛事指定仿真系统对接尚未完成，材料明确标注。"],
        ["能否直接真实飞行？", "不能。程序化城市、代理能耗和离线仿真仅用于规划验证；真实试点还需核验空域、数据、运行许可和安全论证。"],
    ], [44*mm, 111*mm]),
    P("准备提示：现场按通知的 5 分钟讲解、5 分钟问答安排。若演示设备性能不足，优先展示 24 机单项场景，100 机结果使用随包报告佐证。", "small"),
]
save("现场讲稿与专家问答", notes)
