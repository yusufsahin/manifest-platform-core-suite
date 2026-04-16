export const FORM_CONTRACT_VERSION = '1.0.0';

export type JsonSchema = {
  title?: string;
  properties?: Record<string, any>;
  required?: string[];
  'x-form-id'?: string;
  'x-workflow-state'?: string;
  'x-workflow-trigger'?: string;
};

export type FormFieldState = { field_id: string; visible: boolean; readonly: boolean };

export type FormValidationError = { field_id: string; message: string; expr?: string | null };

export type FormValidationResult = { valid: boolean; errors: FormValidationError[] };

export type FormPackage = {
  /** Form payload contract version (not the worker envelope version). */
  formContractVersion: string;
  jsonSchema: JsonSchema;
  uiSchema: Record<string, any>;
  fieldState: FormFieldState[];
  validation: FormValidationResult;
};

export type RemoteFormPackageResponse = {
  request_id?: string;
  duration_ms?: number;
  /** Form payload contract version (snake_case). */
  form_contract_version?: string;
  json_schema?: unknown;
  ui_schema?: unknown;
  field_state?: unknown;
  validation?: unknown;
  diagnostics?: unknown;
};

