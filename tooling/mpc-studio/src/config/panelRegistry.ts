import type { DefinitionCapability, DefinitionDescriptor } from '../types/definition';

export interface PanelRegistryItem {
  id: string;
  label: string;
  group: 'Authoring' | 'Security' | 'Runtime';
  icon:
    | 'FileText'
    | 'Database'
    | 'Shield'
    | 'EyeOff'
    | 'Lock'
    | 'Activity'
    | 'Workflow'
    | 'Layers';
  matchCapabilities: DefinitionCapability[];
  matchKinds?: string[];
}

export const panelRegistry: PanelRegistryItem[] = [
  { id: 'editor', label: 'Manifest Editor', group: 'Authoring', icon: 'FileText', matchCapabilities: [] },
  { id: 'registry', label: 'Domain Registry', group: 'Authoring', icon: 'Database', matchCapabilities: [] },
  {
    id: 'security',
    label: 'Policy Simulator',
    group: 'Security',
    icon: 'Shield',
    matchCapabilities: ['simulate_policy'],
    matchKinds: ['Policy'],
  },
  { id: 'redaction', label: 'Redaction Preview', group: 'Security', icon: 'EyeOff', matchCapabilities: [] },
  {
    id: 'acl',
    label: 'ACL Explorer',
    group: 'Security',
    icon: 'Lock',
    matchCapabilities: ['simulate_acl'],
    matchKinds: ['ACL', 'AccessControl'],
  },
  { id: 'governance', label: 'Governance', group: 'Runtime', icon: 'Activity', matchCapabilities: ['diagnostics'] },
  {
    id: 'workflow',
    label: 'Workflow Engine',
    group: 'Runtime',
    icon: 'Workflow',
    matchCapabilities: ['simulate_workflow'],
    matchKinds: ['Workflow'],
  },
  {
    id: 'overlays',
    label: 'Overlay System',
    group: 'Runtime',
    icon: 'Layers',
    matchCapabilities: ['preview_json'],
    matchKinds: ['Overlay', 'OverlayRule', 'Projection', 'ViewOverlay'],
  },
  {
    id: 'form-preview',
    label: 'Form Preview',
    group: 'Runtime',
    icon: 'Layers',
    matchCapabilities: ['preview_json'],
    matchKinds: ['FormDef'],
  },
];

export function supportsPanel(definition: DefinitionDescriptor | undefined, panelId: string): boolean {
  const panel = panelRegistry.find((item) => item.id === panelId);
  if (!panel) return false;
  if (!definition) return panel.matchCapabilities.length === 0;
  const capabilityMatch = panel.matchCapabilities.every((required) => definition.capabilities.includes(required));
  if (!capabilityMatch) return false;
  if (!panel.matchKinds || panel.matchKinds.length === 0) return true;
  return panel.matchKinds.includes(definition.kind);
}
