export type BaseWidgetProps = {
  inputId: string;
  label: string;
  value: unknown;
  disabled: boolean;
  placeholder?: string;
  onChange: (next: unknown) => void;
  schema: Record<string, any>;
  ui: Record<string, any>;
  className: string;
};

