import { readdir, readFile, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const studioRoot = resolve(process.cwd());
const repoRoot = resolve(studioRoot, '..', '..');
const fixturesRoot = join(repoRoot, 'packages', 'core-conformance', 'fixtures');
const presetsRoot = join(repoRoot, 'packages', 'presets');

const requiredCategories = ['workflow', 'evaluate_integration', 'contracts', 'validator'];
const requiredFiles = ['input.json', 'expected.json', 'meta.json'];

async function listDirectories(path) {
  const entries = await readdir(path, { withFileTypes: true });
  return entries.filter((entry) => entry.isDirectory()).map((entry) => join(path, entry.name));
}

async function assertFile(path) {
  const info = await stat(path);
  if (!info.isFile()) {
    throw new Error(`Expected file but found different type: ${path}`);
  }
}

async function assertJson(path) {
  const content = await readFile(path, 'utf8');
  JSON.parse(content);
}

async function collectPresetNames() {
  const entries = await readdir(presetsRoot, { withFileTypes: true });
  return new Set(
    entries
      .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
      .map((entry) => entry.name.replace(/\.json$/u, '')),
  );
}

async function main() {
  const presetNames = await collectPresetNames();
  let fixtureCount = 0;
  const failures = [];
  const warnings = [];

  for (const category of requiredCategories) {
    const categoryPath = join(fixturesRoot, category);
    let fixtureDirs = [];
    try {
      fixtureDirs = await listDirectories(categoryPath);
    } catch (error) {
      failures.push(`[${category}] missing category folder: ${String(error)}`);
      continue;
    }

    for (const fixturePath of fixtureDirs) {
      fixtureCount += 1;
      for (const fileName of requiredFiles) {
        const fullPath = join(fixturePath, fileName);
        try {
          await assertFile(fullPath);
          await assertJson(fullPath);
        } catch (error) {
          failures.push(`[${category}] ${fixturePath} invalid ${fileName}: ${String(error)}`);
        }
      }

      try {
        const metaPath = join(fixturePath, 'meta.json');
        const meta = JSON.parse(await readFile(metaPath, 'utf8'));
        if (!meta.clock || !meta.preset) {
          warnings.push(`[${category}] ${fixturePath} meta.json missing 'clock' and/or 'preset'; keeping backward compatibility.`);
        }
        if (meta.preset && !presetNames.has(meta.preset)) {
          failures.push(`[${category}] ${fixturePath} unknown preset '${meta.preset}'.`);
        }
      } catch (error) {
        failures.push(`[${category}] ${fixturePath} invalid meta.json semantics: ${String(error)}`);
      }
    }
  }

  if (failures.length > 0) {
    console.error('Conformance gate failed.\n');
    failures.forEach((failure) => console.error(`- ${failure}`));
    process.exit(1);
  }

  if (warnings.length > 0) {
    console.warn('Conformance gate warnings:\n');
    warnings.forEach((warning) => console.warn(`- ${warning}`));
  }

  console.log(`Conformance gate passed for ${fixtureCount} fixtures across ${requiredCategories.length} categories.`);
}

main().catch((error) => {
  console.error('Conformance gate crashed:', error);
  process.exit(1);
});
