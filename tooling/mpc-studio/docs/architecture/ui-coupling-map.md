# UI Coupling Map

## Before Metadata Router

- `src/App.tsx` contained hardcoded `sidebarTab` condition chains for workflow/policy/acl/overlay panels.
- Workflow selection and preview were directly coupled to `listWorkflows()` and `getMermaid()`.
- Sidebar navigation groups were static and not aware of selected definition capabilities.

## After Metadata Router

### Routing Components

- `src/config/panelRegistry.ts`
  - central registry for panel definitions and capability/kind matching rules.
- `src/lib/capabilityRouter.ts`
  - computes menu groups from registry + selected definition.
  - resolves default tab and unsupported panel fallback.
- `src/components/DefinitionInspector.tsx`
  - generic inspector fallback for unknown/new kinds and unmapped capabilities.

### Runtime Contract Coupling

- `src/engine/mpc-engine.ts`
  - `listDefinitions()` replaces workflow-only list logic.
  - `previewDefinition()` and `simulateDefinition()` provide generic operations.
  - v2 envelope unwrapping isolates UI from transport-level shape changes.
- `src/engine/worker.ts`
  - emits descriptor-level metadata with capability hints.
  - routes unknown kinds to `inspector` capability with warning diagnostics.

### UI Entry Points

- `src/App.tsx`
  - drives selector by definition rather than workflow.
  - uses router output to render navigation and tab fallback behavior.
- `src/components/Visualizer.tsx`
  - switches renderer by preview metadata (`mermaid` / `json` / `text`).
- `src/components/Sidebar.tsx`
  - reads dynamic menu groups; no longer owns hardcoded panel topology.

## Known Remaining Couplings

- `WorkflowSimulator` remains workflow-specific by design, now selected through capability routing.
- Governance panel still reads parse-time data directly from validation output.
- End-to-end tests include workflow-heavy scenarios; multi-kind matrix should expand incrementally.
