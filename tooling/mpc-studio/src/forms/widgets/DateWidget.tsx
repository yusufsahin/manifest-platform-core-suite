import type { BaseWidgetProps } from './types';

export function DateWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, onChange, className } = props;
  return (
    <input
      id={inputId}
      aria-label={label}
      type="date"
      value={(value as any) ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={className}
    />
  );
}

