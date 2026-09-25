from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
import pyzipper

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "答辩交付"
PREFIX = "中国民用航空飞行学院+微笑^^调查队"
PASSWORD = os.environ["DEFENSE_ZIP_PASSWORD"].encode("utf-8")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", "dist"}
SKIP_SUFFIXES = {".pyc", ".sqlite3", ".db", ".log", ".wal", ".shm"}

def gather(directory: str):
    return [p for p in (ROOT / directory).rglob("*") if p.is_file() and
            not any(part in SKIP_PARTS for part in p.relative_to(ROOT).parts) and
            p.suffix.lower() not in SKIP_SUFFIXES]

source_files = []
for directory in ("algorithms", "backend", "core", "simulation", "docs", "tests", "scripts", "frontend/src", "frontend/scripts"):
    source_files.extend(gather(directory))
for name in (
    "README.md", "pyproject.toml", "uv.lock", ".python-version", ".env.example", ".gitignore",
    "frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
    "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/README.md",
    "data/demo_report.json", "data/demo_seed.json", "data/demo_smoke.json",
):
    source_files.append(ROOT / name)
source_files += sorted((ROOT / "data/scenarios").glob("*.json"))
source_files = sorted(set(p for p in source_files if p.exists()))

engineering_path = OUT / f"{PREFIX}_仿真工程文件.zip"
with zipfile.ZipFile(engineering_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in ("README.md", ".env.example", "docs/architecture.md", "docs/demo.md", "docs/path-planning.md"):
        z.write(ROOT / name, f"仿真工程/{name}")
    for p in [ROOT / "data/demo_report.json", *sorted((ROOT / "data/scenarios").glob("*.json"))]:
        z.write(p, f"仿真工程/{p.relative_to(ROOT).as_posix()}")
    z.write(OUT / f"{PREFIX}_仿真参数说明.pdf", "仿真工程/仿真参数说明.pdf")
    z.writestr("仿真工程/工程说明.txt", """天枢智航仿真工程资料\n\n本包包含参数说明、环境示例、算法与演示文档及固定种子报告。\n完整源代码另见同前缀的 AES-256 加密 ZIP；解密后在工程根目录按 README.md 运行。\n默认完整场景：seed=42、100 架、最多 600 步；报告记录在 459 仿真秒结束。\n五个单项事件报告位于 data/scenarios/，每项默认 24 架。\n本包不是赛事指定低空运行仿真系统的专用工程格式，也不含真实空域或测绘数据。\n""")

source_path = OUT / f"{PREFIX}_完整源代码_加密.zip"
with pyzipper.AESZipFile(source_path, "w", compression=pyzipper.ZIP_DEFLATED,
                          compresslevel=9, encryption=pyzipper.WZ_AES) as z:
    z.setpassword(PASSWORD)
    z.setencryption(pyzipper.WZ_AES, nbits=256)
    for p in source_files:
        z.write(p, f"天枢智航/{p.relative_to(ROOT).as_posix()}")

with pyzipper.AESZipFile(source_path) as z:
    z.setpassword(PASSWORD)
    bad = z.testzip()
    if bad:
        raise RuntimeError(f"加密包校验失败：{bad}")
    if len(z.namelist()) != len(source_files):
        raise RuntimeError("加密包文件数量不一致")
with zipfile.ZipFile(engineering_path) as z:
    if z.testzip():
        raise RuntimeError("工程包校验失败")

readme_path = OUT / f"{PREFIX}_交付说明.txt"
readme_path.write_text("""城市空中交通规划创新赛交付说明\n\n学校：中国民用航空飞行学院\n队伍：微笑^^调查队\n答辩人：陈奕冰\n\n初赛材料：城市空中交通规划创新方案.pdf、现场答辩定稿.pptx。\n现场辅助：现场讲稿与专家问答.pdf。\n附加任务：仿真工程文件.zip、仿真参数说明.pdf、完整源代码_加密.zip。\n\n源码包为 AES-256 加密 ZIP。密码由参赛队伍另行提供，未写入本说明或工程包。\n工程包使用本项目自建离线仿真引擎；赛事指定仿真系统的专用工程格式尚未获得并适配。\n本项目尚未实现地面车辆协同调度，报告和 PPT 均按现状标注。\n\n现场建议：先展示 24 机单项场景，再用 data/demo_report.json 说明 100 机完整运行；切换场景前导出需保留的报告。\n提交前请由队伍确认原创性承诺、队员信息和赛事要求的签章。\n""", encoding="utf-8")

def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

manifest = {"school": "中国民用航空飞行学院", "team": "微笑^^调查队", "presenter": "陈奕冰",
            "source_file_count": len(source_files), "source_encryption": "AES-256 ZIP",
            "files": [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(OUT.iterdir())
                      if p.is_file() and p.suffix.lower() in {".pdf", ".pptx", ".zip", ".txt"}]}
(OUT / f"{PREFIX}_文件校验清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"engineering": str(engineering_path), "source": str(source_path),
                  "source_files": len(source_files), "manifest": len(manifest["files"])}, ensure_ascii=False))
