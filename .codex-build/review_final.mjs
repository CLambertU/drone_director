import fs from "node:fs/promises";
import path from "node:path";
import { GlobalFonts } from "@napi-rs/canvas";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

GlobalFonts.registerFromPath("C:/Windows/Fonts/msyh.ttc", "Microsoft YaHei");
const workspaceDir = "D:/dorne_competition";
const deckPath = path.join(workspaceDir, "output", "天枢智航_算法设计答辩.pptx");
const previewDir = path.join(workspaceDir, ".codex-build", "final-render");
await fs.mkdir(previewDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(deckPath));
for (let i = 0; i < presentation.slides.items.length; i++) {
  const slide = presentation.slides.items[i];
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({ slideCount: presentation.slides.items.length, previewDir }));
