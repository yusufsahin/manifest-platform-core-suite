export const FORM_FIELD_TYPES = ['string', 'number', 'boolean', 'select', 'multiselect', 'date', 'textarea', 'hidden'] as const;

export const FORMDEF_PROPS = ['title', 'workflowState', 'workflowTrigger', 'fields'] as const;

export const FIELDDEF_PROPS = [
  'type',
  'label',
  'required',
  'default',
  'min',
  'max',
  'options',
  'placeholder',
  'validationExpr',
  'visibilityExpr',
  'readonlyExpr',
] as const;

