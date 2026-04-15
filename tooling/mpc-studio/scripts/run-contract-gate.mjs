import { readdir, readFile, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const studioRoot = resolve(process.cwd());
const contractsRoot = join(studioRoot, 'contracts');
const registryPath = join(contractsRoot, 'error-code-registry.json');
const policyPath = join(contractsRoot, 'contract-policy.json');
const tracesRoot = join(contractsRoot, 'golden-traces');
const workerSnapshotsRoot = join(contractsRoot, 'worker-message-snapshots');

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

function assertWorkerEnvelopeShape(snapshot, fileName) {
  const requiredTopLevel = ['contractVersion', 'requestId', 'timestamp', 'type', 'payload', 'durationMs'];
  for (const key of requiredTopLevel) {
    if (!(key in snapshot)) {
      throw new Error(`[${fileName}] worker envelope missing required key '${key}'`);
    }
  }
  if (typeof snapshot.contractVersion !== 'string' || snapshot.contractVersion !== '2.0.0') {
    throw new Error(`[${fileName}] worker envelope contractVersion must be '2.0.0'`);
  }
  if (typeof snapshot.requestId !== 'string' || snapshot.requestId.length < 6) {
    throw new Error(`[${fileName}] worker envelope requestId must be a non-empty string`);
  }
  if (typeof snapshot.timestamp !== 'string' || Number.isNaN(Date.parse(snapshot.timestamp))) {
    throw new Error(`[${fileName}] worker envelope timestamp must be an ISO date string`);
  }
  if (typeof snapshot.type !== 'string' || snapshot.type.length === 0) {
    throw new Error(`[${fileName}] worker envelope type must be a non-empty string`);
  }
  if (typeof snapshot.durationMs !== 'number' || snapshot.durationMs < 0) {
    throw new Error(`[${fileName}] worker envelope durationMs must be a non-negative number`);
  }
}

function assertFormPackagePayloadShape(payload, fileName) {
  if (!payload || typeof payload !== 'object') {
    throw new Error(`[${fileName}] FORM_PACKAGE payload must be an object`);
  }
  const required = ['jsonSchema', 'uiSchema', 'fieldState', 'validation'];
  for (const key of required) {
    if (!(key in payload)) {
      throw new Error(`[${fileName}] FORM_PACKAGE payload missing '${key}'`);
    }
  }
  const { jsonSchema, uiSchema, fieldState, validation } = payload;
  if (!jsonSchema || typeof jsonSchema !== 'object') {
    throw new Error(`[${fileName}] FORM_PACKAGE jsonSchema must be an object`);
  }
  if (!uiSchema || typeof uiSchema !== 'object') {
    throw new Error(`[${fileName}] FORM_PACKAGE uiSchema must be an object`);
  }
  if (!Array.isArray(fieldState)) {
    throw new Error(`[${fileName}] FORM_PACKAGE fieldState must be an array`);
  }
  fieldState.forEach((row, index) => {
    if (!row || typeof row !== 'object') {
      throw new Error(`[${fileName}] FORM_PACKAGE fieldState[${index}] must be an object`);
    }
    for (const k of ['field_id', 'visible', 'readonly']) {
      if (!(k in row)) {
        throw new Error(`[${fileName}] FORM_PACKAGE fieldState[${index}] missing '${k}'`);
      }
    }
    if (typeof row.field_id !== 'string') {
      throw new Error(`[${fileName}] FORM_PACKAGE fieldState[${index}].field_id must be a string`);
    }
    if (typeof row.visible !== 'boolean' || typeof row.readonly !== 'boolean') {
      throw new Error(`[${fileName}] FORM_PACKAGE fieldState[${index}] visible/readonly must be booleans`);
    }
  });
  if (!validation || typeof validation !== 'object') {
    throw new Error(`[${fileName}] FORM_PACKAGE validation must be an object`);
  }
  if (typeof validation.valid !== 'boolean') {
    throw new Error(`[${fileName}] FORM_PACKAGE validation.valid must be a boolean`);
  }
  if (!Array.isArray(validation.errors)) {
    throw new Error(`[${fileName}] FORM_PACKAGE validation.errors must be an array`);
  }
  validation.errors.forEach((err, index) => {
    if (!err || typeof err !== 'object') {
      throw new Error(`[${fileName}] FORM_PACKAGE validation.errors[${index}] must be an object`);
    }
    if (typeof err.field_id !== 'string' || typeof err.message !== 'string') {
      throw new Error(
        `[${fileName}] FORM_PACKAGE validation.errors[${index}] must include string field_id and message`,
      );
    }
  });
}

function assertDefinitionDescriptorShape(item, fileName, index) {
  const required = ['id', 'name', 'kind', 'version', 'capabilities', 'diagnostics'];
  for (const key of required) {
    if (!(key in item)) {
      throw new Error(`[${fileName}] items[${index}] missing '${key}'`);
    }
  }
  if (!Array.isArray(item.capabilities)) {
    throw new Error(`[${fileName}] items[${index}] capabilities must be array`);
  }
  if (!Array.isArray(item.diagnostics)) {
    throw new Error(`[${fileName}] items[${index}] diagnostics must be array`);
  }
}

function assertWorkerSnapshotShape(snapshot, fileName) {
  assertWorkerEnvelopeShape(snapshot, fileName);
  if (snapshot.type === 'LIST_DEFINITIONS') {
    const items = snapshot.payload?.items;
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error(`[${fileName}] LIST_DEFINITIONS payload.items must contain at least one item`);
    }
    items.forEach((item, index) => assertDefinitionDescriptorShape(item, fileName, index));
    return;
  }
  if (snapshot.type === 'PREVIEW_DEFINITION') {
    const payload = snapshot.payload ?? {};
    const required = ['kind', 'renderer', 'content', 'diagnostics'];
    for (const key of required) {
      if (!(key in payload)) {
        throw new Error(`[${fileName}] PREVIEW_DEFINITION payload missing '${key}'`);
      }
    }
    if (!['mermaid', 'json', 'text'].includes(payload.renderer)) {
      throw new Error(`[${fileName}] PREVIEW_DEFINITION renderer '${payload.renderer}' is not supported`);
    }
    return;
  }
  if (snapshot.type === 'SIMULATE_DEFINITION') {
    const payload = snapshot.payload ?? {};
    const required = ['kind', 'status', 'output', 'diagnostics'];
    for (const key of required) {
      if (!(key in payload)) {
        throw new Error(`[${fileName}] SIMULATE_DEFINITION payload missing '${key}'`);
      }
    }
    if (!['success', 'error'].includes(payload.status)) {
      throw new Error(`[${fileName}] SIMULATE_DEFINITION status '${payload.status}' is invalid`);
    }
    return;
  }
  if (snapshot.type === 'FORM_PACKAGE') {
    assertFormPackagePayloadShape(snapshot.payload, fileName);
    return;
  }
  throw new Error(`[${fileName}] unexpected worker snapshot type '${snapshot.type}'`);
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
  const workerSnapshotEntries = await readdir(workerSnapshotsRoot, { withFileTypes: true });
  const workerSnapshotFiles = workerSnapshotEntries.filter((entry) => entry.isFile() && entry.name.endsWith('.json'));

  if (traceFiles.length === 0) {
    throw new Error('No golden traces found.');
  }
  if (workerSnapshotFiles.length === 0) {
    throw new Error('No worker contract snapshots found.');
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

  for (const entry of workerSnapshotFiles) {
    const fullPath = join(workerSnapshotsRoot, entry.name);
    try {
      const snapshot = await readJson(fullPath);
      assertWorkerSnapshotShape(snapshot, entry.name);
    } catch (error) {
      failures.push(`[${entry.name}] ${String(error)}`);
    }
  }

  if (failures.length > 0) {
    console.error('Contract gate failed.\n');
    failures.forEach((failure) => console.error(`- ${failure}`));
    process.exit(1);
  }

  console.log(
    `Contract gate passed for ${traceFiles.length} golden traces and ${workerSnapshotFiles.length} worker snapshots.`,
  );
}

main().catch((error) => {
  console.error('Contract gate crashed:', error);
  process.exit(1);
});
