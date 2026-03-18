import { readdir, readFile, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const studioRoot = resolve(process.cwd());
const contractsRoot = join(studioRoot, 'contracts');
const registryPath = join(contractsRoot, 'error-code-registry.json');
const policyPath = join(contractsRoot, 'contract-policy.json');
const tracesRoot = join(contractsRoot, 'golden-traces');

async function assertFile(path) {
  const info = await stat(path);
  if (!info.isFile()) {
    throw new Error(`Expected file but found different type: ${path}`);
  }
}

async function readJson(path) {
  await assertFile(path);
  return JSON.parse(await readFile(path, 'utf8'));
}

function assertTraceShape(trace, fileName) {
  const requiredTopLevel = ['contractVersion', 'runId', 'tenantId', 'actorId', 'generatedAt', 'steps', 'summary', 'errors'];
  for (const key of requiredTopLevel) {
    if (!(key in trace)) {
      throw new Error(`[${fileName}] missing required key '${key}'`);
    }
  }
  if (!Array.isArray(trace.steps) || trace.steps.length === 0) {
    throw new Error(`[${fileName}] must contain at least one step`);
  }
}

function parseSemver(version, fileName) {
  const parts = String(version).split('.').map((value) => Number(value));
  if (parts.length !== 3 || parts.some((value) => Number.isNaN(value))) {
    throw new Error(`[${fileName}] invalid semver '${version}'`);
  }
  return { major: parts[0], minor: parts[1], patch: parts[2] };
}

function isVersionSupported(version, policy, fileName) {
  const current = parseSemver(policy.currentVersion, 'contract-policy.json');
  const candidate = parseSemver(version, fileName);
  if (candidate.major !== current.major) {
    return false;
  }
  if (candidate.minor > current.minor) {
    return false;
  }
  const minMinor = Math.max(0, current.minor - Number(policy.deprecationWindow?.minSupportedMinorVersions ?? 1));
  if (candidate.minor < minMinor) {
    return false;
  }
  if (candidate.minor === current.minor) {
    if (candidate.patch > current.patch && !policy.compatibility?.allowPatchForward) {
      return false;
    }
  }
  return true;
}

async function main() {
  const failures = [];
  const registry = await readJson(registryPath);
  const policy = await readJson(policyPath);
  const knownErrorCodes = new Set(registry.errorCodes || []);
  const knownReasonCodes = new Set(registry.reasonCodes || []);

  const traceEntries = await readdir(tracesRoot, { withFileTypes: true });
  const traceFiles = traceEntries.filter((entry) => entry.isFile() && entry.name.endsWith('.json'));

  if (traceFiles.length === 0) {
    throw new Error('No golden traces found.');
  }

  for (const entry of traceFiles) {
    const fullPath = join(tracesRoot, entry.name);
    try {
      const trace = await readJson(fullPath);
      assertTraceShape(trace, entry.name);
      if (!isVersionSupported(trace.contractVersion, policy, entry.name)) {
        failures.push(
          `[${entry.name}] contractVersion '${trace.contractVersion}' unsupported by policy current='${policy.currentVersion}'`,
        );
      }

      for (const step of trace.steps) {
        if (step.errorCode && !knownErrorCodes.has(step.errorCode)) {
          failures.push(`[${entry.name}] unknown errorCode '${step.errorCode}'`);
        }
        for (const err of step.errors || []) {
          if (err.code && !knownErrorCodes.has(err.code)) {
            failures.push(`[${entry.name}] unknown errors[].code '${err.code}'`);
          }
        }
        for (const reason of step.reasons || []) {
          if (reason.code && !knownReasonCodes.has(reason.code)) {
            failures.push(`[${entry.name}] unknown reasons[].code '${reason.code}'`);
          }
        }
      }
    } catch (error) {
      failures.push(`[${entry.name}] ${String(error)}`);
    }
  }

  if (failures.length > 0) {
    console.error('Contract gate failed.\n');
    failures.forEach((failure) => console.error(`- ${failure}`));
    process.exit(1);
  }

  console.log(`Contract gate passed for ${traceFiles.length} golden traces.`);
}

main().catch((error) => {
  console.error('Contract gate crashed:', error);
  process.exit(1);
});
