import type { DefinitionDescriptor } from './definition';

export interface PanelAdapterContext {
  dsl: string;
  selectedDefinition?: DefinitionDescriptor;
  definitions: DefinitionDescriptor[];
  metadataDrivenRouterEnabled: boolean;
}
