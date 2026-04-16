import type { BaseWidgetProps } from './types';

export function SelectWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, onChange, className, schema } = props;
  const options = Array.isArray(schema.enum) ? (schema.enum as string[]) : [];
  return (
    <select
      id={inputId}
      aria-label={label}
      value={(value as any) ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={className}
    >
      <option value="">Seçiniz...</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

