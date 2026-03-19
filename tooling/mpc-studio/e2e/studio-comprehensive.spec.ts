import { expect, test } from '@playwright/test';

async function waitForEngineReady(page: import('@playwright/test').Page) {
  await expect(page.getByText('Local Engine Live')).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/\[ENGINE_ERROR\]/)).toHaveCount(0);
}

async function setStudioDsl(
  page: import('@playwright/test').Page,
  dsl: string,
  definitionId?: string,
) {
  await page.evaluate(
    async ({ dslText, selectedId }) => {
      const studio = (
        window as unknown as {
          __MPC_STUDIO__?: {
            setDsl: (nextDsl: string) => void;
            setSelectedDefinition: (id: string) => void;
          };
        }
      ).__MPC_STUDIO__;
      if (!studio) throw new Error('__MPC_STUDIO__ missing');
      studio.setDsl(dslText);
      await new Promise((resolve) => window.setTimeout(resolve, 900));
      if (selectedId) {
        studio.setSelectedDefinition(selectedId);
      }
    },
    { dslText: dsl, selectedId: definitionId ?? '' },
  );
}

test.describe('MPC Studio comprehensive coverage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForEngineReady(page);
  });

  test('renders all navigation groups and menu items', async ({ page }) => {
    const defaultLabels = [
      'Manifest Editor',
      'Domain Registry',
      'Redaction Preview',
      'Governance',
      'Workflow Engine',
    ];
    for (const label of defaultLabels) {
      await expect(page.getByRole('button', { name: label })).toBeVisible();
    }

    const multikindDsl = `@schema 1
@namespace "demo.dynamic.menu"
@name "dynamic_menu"
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
    await setStudioDsl(page, multikindDsl, 'riskPolicy');
    await expect(page.getByRole('button', { name: 'Policy Simulator' })).toBeVisible();
  });

  test('preview handles workflow, no-workflow and invalid DSL states', async ({ page }) => {
    await expect(page.locator('svg').first()).toBeVisible({ timeout: 15_000 });

    const noWorkflowDsl = `@schema 1
@namespace "demo.minimal"
@name "no_workflow"
@version "1.0.0"

def Policy authz "Auth" {
  rules: []
}`;
    const noWorkflowMermaid = await page.evaluate(async (dsl) => {
      const engine = (window as unknown as { __MPC_ENGINE__?: { getMermaid: (value: string) => Promise<string> } }).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      return engine.getMermaid(dsl);
    }, noWorkflowDsl);
    expect(noWorkflowMermaid.trim()).toBe('');

    const invalidDslResult = await page.evaluate(async (dsl) => {
      const engine = (
        window as unknown as { __MPC_ENGINE__?: { getMermaid: (value: string) => Promise<string> } }
      ).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      try {
        await engine.getMermaid(dsl);
        return { ok: true };
      } catch (error) {
        return { ok: false, message: String(error) };
      }
    }, '@@@ invalid dsl @@@');
    expect(invalidDslResult.ok).toBe(false);
  });

  test('engine lists and renders multiple workflow defs by id', async ({ page }) => {
    const dsl = `@schema 1
@namespace "demo.multi"
@name "multi_workflow"
@version "1.0.0"

def Workflow firstFlow "First" {
  initial: "ALPHA_START"
  states: ["ALPHA_START", "ALPHA_DONE"]
  transitions: [
    {"from": "ALPHA_START", "on": "advance", "to": "ALPHA_DONE"}
  ]
}

def Workflow secondFlow "Second" {
  initial: "BETA_START"
  states: ["BETA_START", "BETA_DONE"]
  transitions: [
    {"from": "BETA_START", "on": "advance", "to": "BETA_DONE"}
  ]
}`;
    const data = await page.evaluate(async (dslText) => {
      const engine = (
        window as unknown as {
          __MPC_ENGINE__?: {
            listWorkflows: (value: string) => Promise<Array<{ id: string; name: string }>>;
            getMermaid: (value: string, workflowId?: string) => Promise<string>;
          };
        }
      ).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      const workflows = await engine.listWorkflows(dslText);
      const first = await engine.getMermaid(dslText, 'firstFlow');
      const second = await engine.getMermaid(dslText, 'secondFlow');
      return { workflows, first, second };
    }, dsl);

    expect(data.workflows.some((item) => item.id === 'firstFlow')).toBe(true);
    expect(data.workflows.some((item) => item.id === 'secondFlow')).toBe(true);
    expect(data.first).toContain('ALPHA_START');
    expect(data.second).toContain('BETA_START');
  });

  test('engine lists multi-kind definitions with metadata capabilities', async ({ page }) => {
    const dsl = `@schema 1
@namespace "demo.multikind"
@name "multi_kind"
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

    const data = await page.evaluate(async (dslText) => {
      const engine = (
        window as unknown as {
          __MPC_ENGINE__?: {
            listDefinitions: (
              value: string,
            ) => Promise<Array<{ id: string; kind: string; capabilities: string[] }>>;
            previewDefinition: (payload: {
              dsl: string;
              definitionId: string;
              kindHint?: string;
            }) => Promise<{ renderer: string; content: string }>;
          };
        }
      ).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      const definitions = await engine.listDefinitions(dslText);
      const preview = await engine.previewDefinition({
        dsl: dslText,
        definitionId: 'riskPolicy',
        kindHint: 'Policy',
      });
      return { definitions, preview };
    }, dsl);

    const workflowDef = data.definitions.find((item) => item.id === 'onboarding');
    const policyDef = data.definitions.find((item) => item.id === 'riskPolicy');

    expect(workflowDef?.kind).toBe('Workflow');
    expect(workflowDef?.capabilities).toContain('simulate_workflow');
    expect(policyDef?.kind).toBe('Policy');
    expect(policyDef?.capabilities).toContain('simulate_policy');
    expect(data.preview.renderer).toBe('json');
    expect(data.preview.content).toContain('rules');
  });

  test('engine marks unknown kinds with inspector capability and fallback diagnostic', async ({ page }) => {
    const dsl = `@schema 1
@namespace "demo.unknown"
@name "unknown_kind"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
  initial: "START"
  states: ["START", "DONE"]
  transitions: [
    {"from": "START", "on": "finish", "to": "DONE"}
  ]
}

def FutureKind canary "Canary Kind" {
  alpha: "beta"
}`;

    const definitions = await page.evaluate(async (dslText) => {
      const engine = (
        window as unknown as {
          __MPC_ENGINE__?: {
            listDefinitions: (
              value: string,
            ) => Promise<
              Array<{
                id: string;
                kind: string;
                capabilities: string[];
                diagnostics: Array<{ code: string; severity: string }>;
              }>
            >;
          };
        }
      ).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      return engine.listDefinitions(dslText);
    }, dsl);

    const unknown = definitions.find((item) => item.id === 'canary');
    expect(unknown?.kind).toBe('FutureKind');
    expect(unknown?.capabilities).toContain('inspector');
    expect(unknown?.diagnostics.some((diagnostic) => diagnostic.code === 'UNKNOWN_KIND_FALLBACK')).toBe(true);
  });

  test('simulateDefinition handles acl and unsupported kind branches', async ({ page }) => {
    const dsl = `@schema 1
@namespace "demo.simdef"
@name "simulate_definition"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
  initial: "START"
  states: ["START", "DONE"]
  transitions: [
    {"from": "START", "on": "finish", "to": "DONE"}
  ]
}`;

    const result = await page.evaluate(async (dslText) => {
      const engine = (
        window as unknown as {
          __MPC_ENGINE__?: {
            simulateDefinition: (payload: {
              dsl: string;
              definitionId?: string;
              kindHint?: string;
              input?: unknown;
            }) => Promise<{
              status: string;
              output: any;
              diagnostics: Array<{ code: string }>;
            }>;
          };
        }
      ).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      const acl = await engine.simulateDefinition({
        dsl: dslText,
        definitionId: 'acl-main',
        kindHint: 'ACL',
        input: { role: 'analyst', action: 'write' },
      });
      const unsupported = await engine.simulateDefinition({
        dsl: dslText,
        definitionId: 'future-main',
        kindHint: 'FutureKind',
        input: {},
      });
      return { acl, unsupported };
    }, dsl);

    expect(result.acl.status).toBe('success');
    expect(result.acl.output.allowed).toBe(false);
    expect(result.unsupported.status).toBe('error');
    expect(result.unsupported.diagnostics.some((diagnostic) => diagnostic.code === 'SIMULATOR_UNSUPPORTED_KIND')).toBe(true);
  });

  test('legacy router query override keeps static sidebar navigation', async ({ page }) => {
    await page.goto('/?metadataDrivenRouter=legacy');
    await waitForEngineReady(page);

    const labels = [
      'Manifest Editor',
      'Domain Registry',
      'Policy Simulator',
      'Redaction Preview',
      'ACL Explorer',
      'Governance',
      'Workflow Engine',
      'Overlay System',
    ];
    for (const label of labels) {
      await expect(page.getByRole('button', { name: label })).toBeVisible();
    }
  });

  test('policy simulator surfaces invalid JSON errors', async ({ page }) => {
    const policyDsl = `@schema 1
@namespace "demo.policy"
@name "policy_test"
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
    await setStudioDsl(page, policyDsl, 'riskPolicy');
    await page.getByRole('button', { name: 'Policy Simulator' }).click();
    await expect(page.getByRole('heading', { name: 'Policy Simulator' })).toBeVisible();

    const editor = page.getByRole('textbox').first();
    await editor.fill('{ invalid json');
    await page.getByRole('button', { name: 'SIMULATE' }).click();

    await expect(page.getByText(/Simulation failed/i)).toBeVisible();
    await expect(page.getByText(/Invalid JSON payload|Expected property name/i)).toBeVisible();
  });

  test('redaction preview masks sensitive sample fields', async ({ page }) => {
    await page.getByRole('button', { name: 'Redaction Preview' }).click();
    await expect(page.getByRole('heading', { name: 'Redaction Preview' })).toBeVisible();

    await page.getByRole('button', { name: 'RUN REDACTION' }).click();
    await expect(page.getByText('[REDACTED_EMAIL]')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('"salary": "[REDACTED]"')).toBeVisible();
    await expect(page.getByText('"ssn": "[REDACTED]"')).toBeVisible();
  });

  test('acl simulator endpoint returns deny/allow decisions', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const engine = (window as unknown as { __MPC_ENGINE__?: { simulateACL: (...args: string[]) => Promise<any> } }).__MPC_ENGINE__;
      if (!engine) throw new Error('__MPC_ENGINE__ missing');
      const denied = await engine.simulateACL('', 'analyst', 'order', 'write');
      const allowed = await engine.simulateACL('', 'admin', 'order', 'write');
      return { denied, allowed };
    });
    expect(result.denied.allowed).toBe(false);
    expect(result.allowed.allowed).toBe(true);
  });

  test('governance panel and capability-driven menu rendering behave as expected', async ({ page }) => {
    await page.getByRole('button', { name: 'Governance' }).click();
    await expect(page.getByRole('heading', { name: 'Governance' })).toBeVisible();
    await expect(page.getByText('No governance findings from current validation run.')).toBeVisible();
    await expect(page.getByText('Policy Health')).toBeVisible();

    const policyDsl = `@schema 1
@namespace "demo.fallback"
@name "fallback_test"
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
    await setStudioDsl(page, policyDsl, 'riskPolicy');
    await expect(page.getByRole('button', { name: 'Policy Simulator' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Workflow Engine' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Policy Simulator' }).click();
    await expect(page.getByRole('heading', { name: 'Policy Simulator' })).toBeVisible();
  });
});
