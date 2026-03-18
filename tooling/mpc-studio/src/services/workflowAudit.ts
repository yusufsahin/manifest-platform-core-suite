import type { WorkflowAuditEvent, WorkflowSession } from '../types/workflow';

export type WorkflowAuditAction = WorkflowAuditEvent['action'];

export function createWorkflowAuditEvent(params: {
  session: WorkflowSession;
  tenantId: string;
  actorId: string;
  action: WorkflowAuditAction;
  allowed: boolean;
  detail?: string;
}): WorkflowAuditEvent {
  const { session, tenantId, actorId, action, allowed, detail } = params;
  return {
    runId: session.runId,
    tenantId,
    actorId,
    action,
    allowed,
    timestamp: new Date().toISOString(),
    detail,
  };
}
