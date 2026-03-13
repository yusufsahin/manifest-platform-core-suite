

interface StatusBadgeProps {
  status: 'loading' | 'ready' | 'error';
}

export const StatusBadge = ({ status }: StatusBadgeProps) => {
  const configs = {
    loading: { color: 'bg-amber-500', text: 'Initializing engine...', pulse: true },
    ready: { color: 'bg-emerald-500', text: 'Local Engine Live', pulse: false },
    error: { color: 'bg-red-500', text: 'Engine Error', pulse: false },
  };

  const config = configs[status];

  return (
    <div className="flex items-center gap-2">
      <div className={`w-1.5 h-1.5 rounded-full ${config.color} ${config.pulse ? 'animate-pulse' : ''} shadow-[0_0_8px_rgba(0,0,0,0.5)]`} />
      <span className="text-[10px] font-medium text-gray-400 tracking-wide">{config.text}</span>
    </div>
  );
};
