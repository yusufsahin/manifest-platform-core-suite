import type { BaseWidgetProps } from './types';

export function TextWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, placeholder, onChange, className } = props;
  return (
    <input
      id={inputId}
      aria-label={label}
      type="text"
      value={(value as any) ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={className}
      placeholder={placeholder}
    />
  );
}

