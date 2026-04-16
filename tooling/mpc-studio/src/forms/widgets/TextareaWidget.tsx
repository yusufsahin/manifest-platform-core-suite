import type { BaseWidgetProps } from './types';

export function TextareaWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, placeholder, onChange, className } = props;
  return (
    <textarea
      id={inputId}
      aria-label={label}
      value={(value as any) ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={className}
      placeholder={placeholder}
      rows={4}
    />
  );
}

