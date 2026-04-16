export type OverlayConflict = { code: string; message: string };

export type OverlayDefinitionSummary = {
  id: string;
  op: string;
  selector?: { kind?: string | null; namespace?: string | null; id?: string | null } | null;
  path?: string | null;
  values?: unknown;
};

export type OverlayNodeDiff = {
  key: string;
  kind: string;
  id: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};

export type OverlayComposeResult = {
  applied: string[];
  conflicts: OverlayConflict[];
  overlays: OverlayDefinitionSummary[];
  diffs: OverlayNodeDiff[];
};

