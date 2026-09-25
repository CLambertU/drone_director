import { pathToFileURL } from 'node:url';
import path from 'node:path';
const m=await import(pathToFileURL(path.join('C:\\Users\\18980\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.923.10815\\skills\\presentations\\container_tools\\artifact_tool_utils.mjs')).href);
console.log(JSON.stringify({font:m.resolvePresentationFont(), fonts:m.PREFERRED_PRESENTATION_FONTS}));
