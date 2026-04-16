import type { BaseWidgetProps } from './types';

export function HiddenWidget(_props: BaseWidgetProps) {
  // Hidden fields are part of the schema but not rendered in preview.
  return null;
}

