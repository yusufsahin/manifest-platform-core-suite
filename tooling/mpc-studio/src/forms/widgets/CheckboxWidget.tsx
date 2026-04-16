import type { BaseWidgetProps } from './types';

export function CheckboxWidget(props: BaseWidgetProps) {
  const { inputId, label, value, disabled, onChange } = props;
  return (
    <input
      id={inputId}
      aria-label={label}
      type="checkbox"
      checked={Boolean(value)}
      disabled={disabled}
      onChange={(e) => onChange(e.target.checked)}
      className="w-4 h-4 rounded accent-violet-500 disabled:opacity-60"
    />
  );
}

