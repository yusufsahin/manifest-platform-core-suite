import type { BaseWidgetProps } from './types';

export function NumberWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, onChange, className, placeholder, schema } = props;
  return (
    <input
      id={inputId}
      aria-label={label}
      type="number"
      value={(value as any) ?? ''}
      disabled={disabled}
      min={schema.minimum}
      max={schema.maximum}
      onChange={(e) => onChange(e.target.valueAsNumber)}
      className={className}
      placeholder={placeholder}
    />
  );
}

