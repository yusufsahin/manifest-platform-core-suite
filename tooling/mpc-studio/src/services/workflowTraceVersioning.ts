import type { WorkflowSession, WorkflowSnapshot } from '../types/workflow';

export function createWorkflowSnapshot(session: WorkflowSession, name?: string): WorkflowSnapshot {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    name: name?.trim() || `snapshot-${new Date(now).toISOString().slice(11, 19).replaceAll(':', '')}`,
    createdAt: now,
    summary: {
      steps: session.steps.length,
      finalState: session.currentState || session.initialState || 'n/a',
    },
    session: structuredClone(session),
  };
}

export function restoreWorkflowSnapshot(snapshot: WorkflowSnapshot): WorkflowSession {
  return {
    ...structuredClone(snapshot.session),
    updatedAt: new Date().toISOString(),
  };
}
