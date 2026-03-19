import { expect, test } from '@playwright/test';

test.describe('worker envelope contract', () => {
  test('returns versioned envelopes for definition APIs', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Local Engine Live')).toBeVisible({ timeout: 60_000 });

    const dsl = `@schema 1
@namespace "demo.contract"
@name "worker_contract"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
  initial: "START"
  states: ["START", "DONE"]
  transitions: [
    {"from": "START", "on": "finish", "to": "DONE"}
  ]
}

def Policy riskPolicy "Risk Policy" {
  rules: []
}`;

    const contract = await page.evaluate(async (dslText) => {
      const engine = (window as unknown as { __MPC_ENGINE__?: any }).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');

      const listEnvelope = await engine.postMessage({
        type: 'LIST_DEFINITIONS',
        payload: { dsl: dslText },
      });
      const previewEnvelope = await engine.postMessage({
        type: 'PREVIEW_DEFINITION',
        payload: { dsl: dslText, definitionId: 'onboarding', kindHint: 'Workflow' },
      });
      const simulateEnvelope = await engine.postMessage({
        type: 'SIMULATE_DEFINITION',
        payload: {
          dsl: dslText,
          definitionId: 'onboarding',
          kindHint: 'Workflow',
          input: { events: ['finish'] },
        },
      });

      return { listEnvelope, previewEnvelope, simulateEnvelope };
    }, dsl);

    for (const envelope of [contract.listEnvelope, contract.previewEnvelope, contract.simulateEnvelope]) {
      expect(envelope.contractVersion).toBe('2.0.0');
      expect(typeof envelope.requestId).toBe('string');
      expect(typeof envelope.timestamp).toBe('string');
      expect(typeof envelope.type).toBe('string');
      expect(Array.isArray(envelope.diagnostics)).toBe(true);
      expect(typeof envelope.durationMs).toBe('number');
      expect(envelope.durationMs).toBeGreaterThanOrEqual(0);
    }

    expect(contract.listEnvelope.type).toBe('LIST_DEFINITIONS');
    expect(Array.isArray(contract.listEnvelope.payload.items)).toBe(true);
    expect(contract.previewEnvelope.type).toBe('PREVIEW_DEFINITION');
    expect(typeof contract.previewEnvelope.payload.renderer).toBe('string');
    expect(contract.simulateEnvelope.type).toBe('SIMULATE_DEFINITION');
    expect(typeof contract.simulateEnvelope.payload.status).toBe('string');
  });
});
