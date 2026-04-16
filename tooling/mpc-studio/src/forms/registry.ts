import { CheckboxWidget } from './widgets/CheckboxWidget';
import { DateWidget } from './widgets/DateWidget';
import { HiddenWidget } from './widgets/HiddenWidget';
import { NumberWidget } from './widgets/NumberWidget';
import { SelectWidget } from './widgets/SelectWidget';
import { TextareaWidget } from './widgets/TextareaWidget';
import { TextWidget } from './widgets/TextWidget';
import type { BaseWidgetProps } from './widgets/types';
import type React from 'react';

export type WidgetId = 'text' | 'number' | 'checkbox' | 'select' | 'date' | 'textarea' | 'hidden';

const REGISTRY: Record<WidgetId, (props: BaseWidgetProps) => React.ReactElement | null> = {
  text: TextWidget,
  number: NumberWidget,
  checkbox: CheckboxWidget,
  select: SelectWidget,
  date: DateWidget,
  textarea: TextareaWidget,
  hidden: HiddenWidget,
};

export function resolveWidgetId(input: {
  jsonSchema: Record<string, any>;
  uiSchema: Record<string, any>;
  fieldId: string;
}): { widget: WidgetId; source: 'uiSchema' | 'schema' | 'default'; requested?: string } {
  const ui = (input.uiSchema?.[input.fieldId] ?? {}) as Record<string, any>;
  const requested = ui['ui:widget'];
  if (typeof requested === 'string' && requested.trim()) {
    const id = requested.trim() as WidgetId;
    if (id in REGISTRY) {
      return { widget: id, source: 'uiSchema', requested };
    }
    return { widget: 'text', source: 'uiSchema', requested };
  }

  const fieldSchema = (input.jsonSchema?.properties?.[input.fieldId] ?? {}) as Record<string, any>;
  if (Array.isArray(fieldSchema.enum) && fieldSchema.enum.length > 0) return { widget: 'select', source: 'schema' };
  if (fieldSchema.type === 'boolean') return { widget: 'checkbox', source: 'schema' };
  if (fieldSchema.type === 'number') return { widget: 'number', source: 'schema' };
  return { widget: 'text', source: 'default' };
}

export function renderWidget(widget: WidgetId, props: BaseWidgetProps): React.ReactElement | null {
  return REGISTRY[widget](props);
}

