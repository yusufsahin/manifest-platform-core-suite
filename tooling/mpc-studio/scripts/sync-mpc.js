import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SOURCE_DIR = path.resolve(__dirname, '../../../src/mpc');
const TARGET_DIR = path.resolve(__dirname, '../public/mpc');

function copyRecursiveSync(src, dest) {
  const exists = fs.existsSync(src);
  const stats = exists && fs.statSync(src);
  const isDirectory = exists && stats.isDirectory();
  if (isDirectory) {
    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest, { recursive: true });
    }
    fs.readdirSync(src).forEach((childItemName) => {
      copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
    });
  } else {
    fs.copyFileSync(src, dest);
  }
}

console.log(`Syncing MPC core from ${SOURCE_DIR} to ${TARGET_DIR}...`);

if (!fs.existsSync(SOURCE_DIR)) {
  console.error(`Source directory ${SOURCE_DIR} does not exist!`);
  process.exit(1);
}

// Clean target directory
if (fs.existsSync(TARGET_DIR)) {
  fs.rmSync(TARGET_DIR, { recursive: true, force: true });
}

copyRecursiveSync(SOURCE_DIR, TARGET_DIR);

console.log('✓ MPC core synced successfully.');

// Generate file manifest for the worker
const manifest = [];
function walk(dir, base) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const relPath = path.posix.join(base, file);
    if (fs.statSync(fullPath).isDirectory()) {
      walk(fullPath, relPath);
    } else {
      manifest.push(relPath);
    }
  }
}

walk(TARGET_DIR, '');
fs.writeFileSync(path.join(TARGET_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`✓ Generated manifest.json with ${manifest.length} files.`);
