export const DEFINITION_CONTRACT_VERSION = '2.0.0';

export type DefinitionCapability =
  | 'preview_mermaid'
  | 'preview_json'
  | 'simulate_workflow'
  | 'simulate_policy'
  | 'simulate_acl'
  | 'diagnostics'
  | 'inspector';

export const DEFINITION_CAPABILITIES: ReadonlySet<DefinitionCapability> = new Set([
  'preview_mermaid',
  'preview_json',
  'simulate_workflow',
  'simulate_policy',
  'simulate_acl',
  'diagnostics',
  'inspector',
]);

export interface DefinitionDiagnostic {
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
}

export interface DefinitionDescriptor {
  id: string;
  name: string;
  kind: string;
  version: string;
  capabilities: DefinitionCapability[];
  diagnostics: DefinitionDiagnostic[];
}

export interface DefinitionPreviewResult {
  kind: string;
  definitionId?: string;
  renderer: 'mermaid' | 'json' | 'text';
  content: string;
  diagnostics: DefinitionDiagnostic[];
}

export interface DefinitionSimulationResult {
  kind: string;
  definitionId?: string;
  status: 'success' | 'error';
  output: unknown;
  diagnostics: DefinitionDiagnostic[];
}

export interface WorkerEnvelope<TPayload> {
  contractVersion: string;
  requestId: string;
  timestamp: string;
  type: string;
  payload: TPayload;
  diagnostics?: DefinitionDiagnostic[];
  durationMs?: number;
  errorCode?: string;
}

export function isDefinitionCapability(value: string): value is DefinitionCapability {
  return DEFINITION_CAPABILITIES.has(value as DefinitionCapability);
}

export function normalizeDefinitionDescriptor(raw: unknown): DefinitionDescriptor {
  const fallback: DefinitionDescriptor = {
    id: 'unknown-definition',
    name: 'Unknown Definition',
    kind: 'Unknown',
    version: '1.0.0',
    capabilities: ['inspector', 'diagnostics'],
    diagnostics: [],
  };
  if (!raw || typeof raw !== 'object') {
    return fallback;
  }

  const value = raw as Partial<DefinitionDescriptor> & { capabilities?: unknown; diagnostics?: unknown };
  const id = typeof value.id === 'string' && value.id.trim() ? value.id.trim() : fallback.id;
  const name = typeof value.name === 'string' && value.name.trim() ? value.name.trim() : id;
  const kind = typeof value.kind === 'string' && value.kind.trim() ? value.kind.trim() : fallback.kind;
  const version = typeof value.version === 'string' && value.version.trim() ? value.version.trim() : fallback.version;

  const rawCapabilities = Array.isArray(value.capabilities) ? (value.capabilities as unknown[]) : [];
  const capabilities =
    rawCapabilities.length > 0
      ? rawCapabilities
          .filter((item): item is string => typeof item === 'string')
          .filter((item): item is DefinitionCapability => isDefinitionCapability(item))
      : fallback.capabilities;

  const diagnostics = Array.isArray(value.diagnostics)
    ? value.diagnostics
        .filter((item): item is DefinitionDiagnostic => {
          if (!item || typeof item !== 'object') return false;
          const diagnostic = item as Partial<DefinitionDiagnostic>;
          return (
            typeof diagnostic.code === 'string' &&
            typeof diagnostic.message === 'string' &&
            (diagnostic.severity === 'info' || diagnostic.severity === 'warning' || diagnostic.severity === 'error')
          );
        })
        .map((item) => ({
          code: item.code.trim() || 'UNKNOWN_DIAGNOSTIC',
          message: item.message,
          severity: item.severity,
        }))
    : [];

  return {
    id,
    name,
    kind,
    version,
    capabilities: capabilities.length > 0 ? capabilities : fallback.capabilities,
    diagnostics,
  };
}

