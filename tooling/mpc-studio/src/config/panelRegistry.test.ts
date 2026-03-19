import { describe, expect, it } from 'vitest';
import { supportsPanel } from './panelRegistry';
import type { DefinitionDescriptor } from '../types/definition';

function makeDefinition(
  overrides: Partial<DefinitionDescriptor> = {},
): DefinitionDescriptor {
  return {
    id: 'def-1',
    name: 'Definition One',
    kind: 'Workflow',
    version: '1.0.0',
    capabilities: ['preview_mermaid', 'simulate_workflow', 'diagnostics'],
    diagnostics: [],
    ...overrides,
  };
}

describe('supportsPanel', () => {
  it('returns false for unknown panel id', () => {
    expect(supportsPanel(undefined, 'missing-panel')).toBe(false);
  });

  it('allows static panels without a definition', () => {
    expect(supportsPanel(undefined, 'editor')).toBe(true);
    expect(supportsPanel(undefined, 'registry')).toBe(true);
  });

  it('blocks capability-driven panels without a definition', () => {
    expect(supportsPanel(undefined, 'workflow')).toBe(false);
    expect(supportsPanel(undefined, 'security')).toBe(false);
  });

  it('matches workflow panel by capability and kind', () => {
    const definition = makeDefinition();
    expect(supportsPanel(definition, 'workflow')).toBe(true);
  });

  it('blocks panel when capability is missing', () => {
    const definition = makeDefinition({ capabilities: ['diagnostics'] });
    expect(supportsPanel(definition, 'workflow')).toBe(false);
  });

  it('blocks panel when kind does not match required kinds', () => {
    const definition = makeDefinition({
      kind: 'Policy',
      capabilities: ['simulate_workflow', 'diagnostics'],
    });
    expect(supportsPanel(definition, 'workflow')).toBe(false);
  });

  it('allows panel with no kind restriction when capability exists', () => {
    const definition = makeDefinition({
      kind: 'Policy',
      capabilities: ['simulate_policy', 'diagnostics'],
    });
    expect(supportsPanel(definition, 'governance')).toBe(true);
  });
});
