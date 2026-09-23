import { cpSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const root = fileURLToPath(new URL('..', import.meta.url));
const target = resolve(root, 'public/cesium');
mkdirSync(target, { recursive: true });
for (const directory of ['Assets', 'ThirdParty', 'Widgets', 'Workers']) {
  cpSync(resolve(root, 'node_modules/cesium/Build/Cesium', directory), resolve(target, directory), { recursive: true });
}
