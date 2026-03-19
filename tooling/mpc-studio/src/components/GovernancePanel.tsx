import { Activity, AlertTriangle, CheckCircle2, Shield } from 'lucide-react';
import type { PanelAdapterContext } from '../types/panelAdapter';

interface ValidationError {
  code: string;
  severity: string;
  message: string;
}

interface GovernancePanelProps {
  namespace?: string;
  astHash?: string;
  errors: ValidationError[];
  definitionCount: number;
  context?: PanelAdapterContext;
}

const GovernancePanel = ({ namespace, astHash, errors, definitionCount, context }: GovernancePanelProps) => {
  const criticalCount = errors.filter((error) => error.severity === 'error' || error.severity === 'fatal').length;
  const warningCount = errors.filter((error) => error.severity === 'warning' || error.severity === 'warn').length;
  const isHealthy = criticalCount === 0;

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center gap-2">
        <Activity className="w-4 h-4 text-amber-400" />
        <h2 className="text-xs font-bold uppercase tracking-widest text-white">Governance</h2>
        {context?.selectedDefinition ? (
          <span className="ml-auto text-[10px] text-amber-200/80 font-mono">
            {context.selectedDefinition.kind}:{context.selectedDefinition.id}
          </span>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3 p-3 border-b border-white/5">
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Policy Health</p>
          <p className={`text-sm font-mono mt-1 ${isHealthy ? 'text-emerald-400' : 'text-amber-400'}`}>
            {isHealthy ? 'PASS' : 'REVIEW_REQUIRED'}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Definitions</p>
          <p className="text-sm font-mono text-cyan-300 mt-1">{definitionCount}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">Namespace</p>
          <p className="text-xs font-mono text-violet-300 mt-1 truncate">{namespace || 'none'}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <p className="text-[10px] uppercase text-gray-500">AST Hash</p>
          <p className="text-xs font-mono text-gray-300 mt-1 truncate">{astHash || 'pending...'}</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-2">
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-[11px] text-gray-300">
            <Shield className="w-3.5 h-3.5 text-cyan-400" />
            Contract + validation status
          </div>
          <div className="text-[11px] font-mono text-gray-300">
            {criticalCount} critical / {warningCount} warnings
          </div>
        </div>

        {errors.length === 0 ? (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-[11px] text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            No governance findings from current validation run.
          </div>
        ) : (
          errors.map((error, index) => (
            <div
              key={`${error.code}-${index}`}
              className={`rounded-xl border p-3 text-[11px] ${
                error.severity === 'error' || error.severity === 'fatal'
                  ? 'border-red-500/30 bg-red-500/10 text-red-300'
                  : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
              }`}
            >
              <div className="flex items-center gap-2 font-mono mb-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                [{error.code}] {String(error.severity || 'warn').toUpperCase()}
              </div>
              <div>{error.message}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default GovernancePanel;
