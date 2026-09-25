import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const workspaceDir = 'D:/dorne_competition';
const buildDir = path.join(workspaceDir, '.codex-build/defense');
const previewDir = path.join(buildDir, 'slide_render');
const finalDir = path.join(workspaceDir, 'output/答辩交付');
const finalPath = path.join(finalDir, '中国民用航空飞行学院+微笑^^调查队_现场答辩定稿.pptx');
const SKILL_DIR = 'C:/Users/18980/.codex/plugins/cache/openai-primary-runtime/presentations/26.923.10815/skills/presentations';
const RUNTIME_PYTHON = 'C:/Users/18980/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href);

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
await fs.mkdir(finalDir, { recursive: true });

const W = 1280, H = 720;
const BG = '#0B1723', FG = '#F2FAFB', MUTED = '#ADC1C8', TEAL = '#69E1CD', AMBER = '#FFBF77';
const FONT = 'Microsoft YaHei';
const deck = Presentation.create({ slideSize: { width: W, height: H } });
const allSlides = [];
process.env.RUNTIME_NODE_MODULES = 'C:/Users/18980/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
function txt(slide, text, left, top, width, height, fontSize=24, color=FG, bold=false) {
  const shape = slide.shapes.add({ geometry: 'textbox', position: { left, top, width, height }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = text;
  shape.text.style = { typeface: FONT, fontSize, color, bold, autoFit: 'none' };
  return shape;
}
function make(title, n, notes, appendix=false) {
  const s = deck.slides.add();
  allSlides.push(s);
  s.background.fill = BG;
  txt(s, title, 64, 44, 1138, 64, 40, FG, true);
  txt(s, appendix ? '专家问答备查' : '天枢智航  城市低空交通智能规划与自主协同系统', 66, 670, 1030, 27, 15, MUTED);
  txt(s, String(n).padStart(2, '0'), 1150, 669, 70, 28, 16, TEAL, true);
  s.speakerNotes.textFrame.setText(notes);
  return s;
}
function label(s, num, title, desc, x, y, w) {
  txt(s, num, x, y, w, 76, 56, TEAL, true);
  txt(s, title, x, y+91, w, 52, 30, FG, true);
  txt(s, desc, x, y+159, w, 180, 22, MUTED);
}

let s = deck.slides.add();
allSlides.push(s);
s.background.fill = BG;
txt(s, '天枢智航', 67, 185, 960, 100, 68, FG, true);
txt(s, '城市低空交通智能规划与自主协同系统', 72, 295, 1040, 63, 31, TEAL);
txt(s, '城市空中交通规划创新赛  |  5 分钟项目讲解', 72, 440, 940, 38, 22, MUTED);
txt(s, '中国民用航空飞行学院  ·  微笑^^调查队  ·  陈奕冰', 72, 559, 1030, 35, 20, FG);
s.speakerNotes.textFrame.setText('0:00-0:15。各位评委好，我是陈奕冰，来自中国民用航空飞行学院微笑^^调查队。作品天枢智航是一套城市低空交通规划与自主协同仿真系统。今天展示动态扰动下的航路规划、安全处置与可核查运行记录。');

s = make('城市低空运行的三个决策问题', 2,
  '0:15-0:45。城市低空规划不能只找最短路。建筑、临时管制和雷暴决定能否飞，容量与任务压力影响效率，多架飞行器还可能在未来几秒相遇。我们把可行性、路线代价和冲突处置放在同一运行闭环。');
label(s, '01', '哪里可飞', '建筑与城市边界\n空域管制与雷暴\n航路容量', 75, 160, 315);
label(s, '02', '怎样更优', '距离与风险\n拥堵与气象\n爬升能耗代理', 465, 160, 315);
label(s, '03', '如何安全', '未来轨迹相交\n同一时刻双向间隔\n可执行的解脱动作', 855, 160, 315);

s = make('从环境快照到安全执行', 3,
  '0:45-1:20。系统从三维城市与任务读取一致快照，先过滤不可飞航段，再规划航路。仿真引擎逐步推进飞机，事件注入后重规划；服务端通过 WebSocket 把状态传给三维控制台，图表与事件结果都来自真实仿真快照。来源：docs/architecture.md、docs/demo.md。');
const flow = [
  ['01', '读取一致快照', '航路图、天气、管制、容量、任务'],
  ['02', '规划安全航路', '硬约束筛边，五项加权 A* 输出代价分解'],
  ['03', '预测并解脱冲突', '连续轨迹检测，候选动作全机复检'],
  ['04', '推进与反馈', '实际运动、事件结果、三维看板和报告'],
];
flow.forEach((r,i)=>{ const y=150+i*115; txt(s,r[0],75,y,100,55,39,TEAL,true); txt(s,r[1],185,y,340,50,29,FG,true); txt(s,r[2],560,y+3,620,58,22,MUTED); });
txt(s, '算法只读取状态快照；环境变化后再规划、再复检。', 75, 605, 1090, 38, 21, AMBER);

s = make('五项加权 A* 与硬约束', 4,
  '1:20-2:10。规划器先剔除建筑碰撞、关闭空域、雷暴和超容量航段，再在可行图上最小化距离、风险、拥堵、爬升能耗代理和天气五项代价。默认权重为 1、2、1.5、0.8、3。启发值只使用三维直线距离的距离项，因此在本快照可行图上不会高估剩余代价。航程超限回退不保证加权最优。来源：docs/path-planning.md、backend/config/settings.py。');
txt(s, '先排除不可飞航段', 75, 151, 470, 55, 33, TEAL, true);
txt(s, '建筑、边界、雷暴\n临时管制、容量上限', 75, 225, 480, 125, 24, FG);
txt(s, '再比较可行路线', 650, 151, 520, 55, 33, TEAL, true);
txt(s, '距离   风险   拥堵\n爬升能耗代理   气象', 650, 225, 520, 125, 24, FG);
txt(s, '路径总代价 = 距离 + 风险 + 拥堵 + 能耗代理 + 气象', 75, 425, 1120, 62, 30, FG, true);
txt(s, '各项分别乘以非负权重  1 / 2 / 1.5 / 0.8 / 3；结果返回代价分解', 75, 530, 1110, 42, 21, MUTED);

s = make('连续预测与全机安全复检', 5,
  '2:10-2:55。默认 10 秒预测窗内，对分段线性轨迹计算共同时间区间。只有同一时刻水平距离不大于 30 米且垂直距离不大于 15 米才判冲突。调速、调高、改航、延迟候选都从实际位置连续衔接，并对全机复检。没有安全候选则暂停运行。阈值是仿真默认值，并非法规标准。来源：simulation/engine/safety.py、backend/config/settings.py。');
txt(s, '10 s', 75, 160, 260, 90, 64, TEAL, true);
txt(s, '预测窗', 75, 260, 260, 47, 25, MUTED);
txt(s, '30 m', 420, 160, 300, 90, 64, FG, true);
txt(s, '水平间隔', 420, 260, 300, 47, 25, MUTED);
txt(s, '15 m', 795, 160, 300, 90, 64, FG, true);
txt(s, '垂直间隔', 795, 260, 300, 47, 25, MUTED);
txt(s, '候选动作：调速 · 调高 · 改航 · 延迟', 75, 393, 1090, 50, 30, FG, true);
txt(s, '每个候选都要满足硬约束和全机间距；没有安全解则留痕并暂停。', 75, 482, 1110, 78, 24, AMBER);

s = make('现场系统与动态场景', 6,
  '2:55-3:55。现场选择一个单项事件。例如雷暴或管制覆盖在飞飞机，系统先让区内飞机撤离，再沿新航路继续任务；故障场景把飞机真正推进至备降点。右侧为实时指标，底部事件可展开处置结果。截图为本地程序化仿真城市，不是真实空域。来源：本地控制台、docs/demo.md。');
const shot = new Uint8Array(await fs.readFile(path.join(workspaceDir, 'output/答辩控制台总览.png')));
s.images.add({ blob: shot, contentType: 'image/png', alt: '本地三维仿真控制台总览', fit: 'contain', position: { left: 60, top: 145, width: 710, height: 495 } });
txt(s, '五个单项场景', 830, 165, 350, 56, 30, TEAL, true);
txt(s, '航路拥堵\n东部雷暴\n临时管制\n故障备降\n两机冲突', 830, 235, 360, 270, 27, FG);
txt(s, '地图、指标、事件记录均由仿真快照驱动。', 830, 542, 365, 75, 20, MUTED);

s = make('固定种子 100 机完整演示', 7,
  '3:55-4:35。seed=42 的 100 机完整演示在 459 个仿真秒结束。99 项任务抵达原目的地，1 架故障机实际备降，记录 30 次规则解脱，最终剩余冲突 0。累计实际飞行 305.09 公里。这里是一次可复现实测，不是跨场景安全保证。来源：data/demo_report.json。');
const results = [
  ['99/100', '原任务完成'],
  ['1', '真实备降'],
  ['30', '规则解脱'],
  ['0', '最终剩余冲突'],
];
results.forEach((r,i)=>{const x=72+i*302;txt(s,r[0],x,220,275,95,56,i===3?TEAL:FG,true);txt(s,r[1],x,333,275,64,23,MUTED);});
txt(s, 'seed = 42   ·   459 仿真秒   ·   累计飞行 305.09 km', 72, 490, 1100, 54, 26, TEAL, true);
txt(s, '结果来自 data/demo_report.json 的单次可复现实测。', 72, 567, 1100, 42, 18, MUTED);

s = make('工程边界与落地路径', 8,
  '4:35-5:00。已交付可运行的算法、仿真、服务、控制台和报告。能耗与天气仍是工程代理模型；地面车辆协同和赛事指定仿真平台接口没有完成。真实试点必须引入经核验的空域、气象、机型数据，在适用许可与安全管理要求下验证。来源：README.md、docs/architecture.md、中国民航局《无人驾驶航空器飞行管理暂行条例》《民用无人驾驶航空器运行安全管理规则》。https://www.caac.gov.cn/XXGK/XXGK/FLFG/202401/t20240115_222642.html；https://app.caac.gov.cn/XXGK/XXGK/MHGZ/202401/t20240103_222566.html');
txt(s, '已交付', 75, 155, 465, 55, 31, TEAL, true);
txt(s, '规划与冲突算法\n动态事件仿真\n三维监控与报告\n可复现工程源码', 75, 235, 490, 270, 25, FG);
txt(s, '下一步', 670, 155, 455, 55, 31, AMBER, true);
txt(s, '接入真实数据与机型模型\n补齐地面车辆协同\n适配赛事指定平台\n完成运行许可与安全论证', 670, 235, 520, 270, 25, FG);
txt(s, '当前成果用于竞赛仿真与规划验证，不等同于真实飞行许可。', 75, 578, 1100, 42, 21, MUTED);

s = make('备查：关键默认参数', 9,
  '专家问答备查。来源：backend/config/settings.py、docs/path-planning.md。', true);
const rows = [
  ['规划权重', '距离 1  /  风险 2  /  拥堵 1.5  /  能耗 0.8  /  气象 3'],
  ['冲突阈值', '水平 30 m  /  垂直 15 m  /  预测窗 10 s'],
  ['仿真步长', '1 仿真秒，默认目标倍率 10×'],
  ['坐标模型', 'ENU 米制，程序化建筑与分层有向航路'],
];
rows.forEach((r,i)=>{const y=160+i*105;txt(s,r[0],75,y,260,50,26,TEAL,true);txt(s,r[1],360,y,830,65,23,FG);});

s = make('备查：结果与能力边界', 10,
  '专家问答备查。说明：100 机结果为固定种子一次运行；无已训练 AI 决策器，地面车辆协同未完成。来源：data/demo_report.json、docs/demo.md、README.md。', true);
txt(s, '100 机报告', 75, 157, 440, 53, 30, TEAL, true);
txt(s, '99 项原任务完成；1 架真实备降\n30 次规则解脱；最终剩余冲突 0\n仿真推进 459 秒，实际耗时约 47.9 秒', 75, 235, 1090, 205, 25, FG);
txt(s, '口径说明', 75, 485, 350, 50, 30, AMBER, true);
txt(s, '备降不计入原任务完成。当前能耗和天气为代理模型，无已训练 AI 决策器。', 75, 545, 1100, 78, 22, MUTED);

const candidatePath = path.join(buildDir, 'candidate-defense.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
for (let i=0;i<allSlides.length;i++) {
  const slide = allSlides[i];
  const png = await deck.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(path.join(previewDir, `slide-${String(i+1).padStart(2,'0')}.png`), new Uint8Array(await png.arrayBuffer()));
}
const result = await finalizePresentation({
  explicitTotalSlideCount: 10,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL_DIR, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-heading-fit'],
  fontPolicy: { basis: 'design', families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, 'defense-final.validation.json'),
});
console.log(JSON.stringify({ finalPath, result }, null, 2));
