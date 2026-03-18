import { expect, test } from '@playwright/test';

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[index];
}

test('workflow benchmark p50/p95', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Local Engine Live')).toBeVisible({ timeout: 60_000 });
  const raw = await page.evaluate(async () => {
    const engine = (window as unknown as { __MPC_ENGINE__?: any }).__MPC_ENGINE__;
    if (!engine) {
      throw new Error('__MPC_ENGINE__ is not available');
    }
    const dsl = `@schema 1
@namespace "demo.crm"
@name "customer_flow"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
    initial: "START"
    states: ["START", "QUALIFYING", "DONE"]
    transitions: [
        {"from": "START", "on": "begin", "to": "QUALIFYING"},
        {"from": "QUALIFYING", "on": "finish", "to": "DONE"}
    ]
}`;
    const limits = { maxSteps: 100, maxPayloadBytes: 16384, maxEventNameLength: 128 };

    const stepDurations: number[] = [];
    const runDurations: number[] = [];
    const exportDurations: number[] = [];

    let currentState = '';
    let initialState = '';
    for (let i = 0; i < 10; i += 1) {
      const t0 = performance.now();
      const response = await engine.workflowStep({
        dsl,
        event: i % 2 === 0 ? 'begin' : 'finish',
        context: { source: 'benchmark', iteration: i },
        currentState: currentState || undefined,
        initialState: initialState || undefined,
        actorId: 'benchmark-user',
        actorRoles: ['admin'],
        tenantId: 'tenant-benchmark',
        limits,
      });
      stepDurations.push(performance.now() - t0);
      currentState = response.currentState;
      initialState = response.initialState;
    }

    for (let i = 0; i < 6; i += 1) {
      const t0 = performance.now();
      await engine.workflowRun({
        dsl,
        events: [{ event: 'begin' }, { event: 'finish' }],
        actorId: 'benchmark-user',
        actorRoles: ['admin'],
        tenantId: 'tenant-benchmark',
        limits,
      });
      runDurations.push(performance.now() - t0);
    }

    const exportSession = {
      runId: crypto.randomUUID(),
      tenantId: 'tenant-benchmark',
      actorId: 'benchmark-user',
      initialState: 'START',
      currentState: 'DONE',
      availableTransitions: [],
      steps: [],
      auditTrail: [
        {
          runId: 'run-bench',
          tenantId: 'tenant-benchmark',
          actorId: 'benchmark-user',
          action: 'run',
          allowed: true,
          timestamp: new Date().toISOString(),
          detail: 'bench+1@example.com token-skABCDEF12345',
        },
      ],
      updatedAt: new Date().toISOString(),
    };
    for (let i = 0; i < 6; i += 1) {
      const t0 = performance.now();
      engine.exportWorkflowTrace(exportSession);
      exportDurations.push(performance.now() - t0);
    }

    return { stepDurations, runDurations, exportDurations };
  });
  const metrics = {
    step: { p50: percentile(raw.stepDurations, 50), p95: percentile(raw.stepDurations, 95) },
    run: { p50: percentile(raw.runDurations, 50), p95: percentile(raw.runDurations, 95) },
    export: { p50: percentile(raw.exportDurations, 50), p95: percentile(raw.exportDurations, 95) },
  };

  console.log(`BENCHMARK ${JSON.stringify(metrics)}`);

  const enforce = process.env.MPC_BENCHMARK_ENFORCE === 'true';
  if (enforce) {
    expect(metrics.step.p95).toBeLessThan(120);
    expect(metrics.run.p95).toBeLessThan(300);
    expect(metrics.export.p95).toBeLessThan(500);
  }
});
