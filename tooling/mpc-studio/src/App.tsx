import { useState, useEffect, useMemo, useRef } from 'react';
import { mpcEngine, type RuleArtifactSummary } from './engine/mpc-engine';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ManifestEditor from './components/ManifestEditor';
import Visualizer from './components/Visualizer';
import DebugPanel from './components/DebugPanel';
import DomainRegistry from './components/DomainRegistry';
import PolicySimulator from './components/PolicySimulator';
import WorkflowSimulator from './components/WorkflowSimulator';
import RedactionPreview from './components/RedactionPreview';
import ACLExplorer from './components/ACLExplorer';
import GovernancePanel from './components/GovernancePanel';
import OverlaySystemPanel from './components/OverlaySystemPanel';
import UISchemaView from './components/UISchemaView';
import DefinitionInspector from './components/DefinitionInspector';
import FormPreview from './components/FormPreview';
import { StatusBadge } from './components/StatusBadge';
import { redactUnknown } from './lib/redaction';
import type { DefinitionDescriptor } from './types/definition';
import type { PanelAdapterContext } from './types/panelAdapter';
import {
  resolveDefaultSidebarTab,
  resolveSidebarMenu,
  shouldUseFallbackInspector,
} from './lib/capabilityRouter';

const VALIDATION_DEBOUNCE_MS = 350;

interface ValidationError {
  code: string;
  message: string;
  severity: string;
  line?: number;
  col?: number;
  end_line?: number;
  end_col?: number;
}

interface ValidationResult {
  status: string;
  namespace?: string;
  ast_hash?: string;
  errors: ValidationError[];
  ast?: {
    defs: Array<{ kind: string; id: string; name?: string; properties: any }>;
  };
}

const DEFAULT_DSL = `@schema 1
@namespace "demo.crm"
@name "customer_flow"
@version "1.0.0"

def Workflow onboarding "Onboarding" {
    initial: "START"
    states: ["START", "QUALIFYING", "DONE"]
    final_states: ["DONE"]
    transitions: [
        {"from": "START", "on": "begin", "to": "QUALIFYING"},
        {"from": "QUALIFYING", "on": "finish", "to": "DONE"}
    ]
}`;

function App() {
  const metadataDrivenRouterEnabled = useMemo(() => {
    const envEnabled = import.meta.env.VITE_METADATA_DRIVEN_ROUTER !== 'false';
    const params = new URLSearchParams(window.location.search);
    const override = String(params.get('metadataDrivenRouter') ?? '').toLowerCase().trim();
    if (override === 'legacy' || override === 'off' || override === 'false') {
      return false;
    }
    if (override === 'metadata' || override === 'on' || override === 'true') {
      return true;
    }
    return envEnabled;
  }, []);
  const devWindow = window as Window & {
    __MPC_ENGINE__?: typeof mpcEngine;
    __MPC_STUDIO__?: {
      setDsl: (nextDsl: string) => void;
      setSelectedDefinition: (definitionId: string) => void;
      setSidebarTab: (tab: string) => void;
    };
  };

  if (import.meta.env.DEV) {
    devWindow.__MPC_ENGINE__ = mpcEngine;
    devWindow.__MPC_STUDIO__ = {
      setDsl: (nextDsl: string) => setDsl(nextDsl),
      setSelectedDefinition: (definitionId: string) => setSelectedDefinitionId(definitionId),
      setSidebarTab: (tab: string) => setSidebarTab(tab),
    };
  }

  const [dsl, setDsl] = useState(DEFAULT_DSL);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [fileHandle, setFileHandle] = useState<FileSystemFileHandle | null>(null);
  const [folderHandle, setFolderHandle] = useState<FileSystemDirectoryHandle | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [activeFileName, setActiveFileName] = useState('Main.manifest');
  const [debugMode, setDebugMode] = useState(false);
  const [debugResult, setDebugResult] = useState<{ value: any; type: string | null; trace: any[] | null } | null>(null);
  const [activeTab, setActiveTab ] = useState<'preview' | 'debug' | 'ui'>('preview');
  const [sidebarTab, setSidebarTab] = useState('editor');
  const [engineError, setEngineError] = useState<string | null>(null);
  const [artifactItems, setArtifactItems] = useState<RuleArtifactSummary[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string>('');
  const [selectedArtifactStatus, setSelectedArtifactStatus] = useState<string>('');
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [artifactStatusMessage, setArtifactStatusMessage] = useState<string>('');
  const [definitionItems, setDefinitionItems] = useState<DefinitionDescriptor[]>([]);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<string>('');
  const [formPreviewFormId, setFormPreviewFormId] = useState<string>('');
  const [formPreviewWorkflowId, setFormPreviewWorkflowId] = useState<string>('');
  const [formPreviewActorId, setFormPreviewActorId] = useState<string>('operator-1');
  const [formPreviewActorRolesInput, setFormPreviewActorRolesInput] = useState<string>('user');
  const [formPreviewActorAttrsJson, setFormPreviewActorAttrsJson] = useState<string>('{}');
  const validationTimeoutRef = useRef<number | null>(null);
  const queryParams = new URLSearchParams(window.location.search);
  const tenantFromUrl = queryParams.get('tenant_id') || 'tenant-default';
  const runtimeFromUrl = queryParams.get('runtime');
  const useTenantActiveManifest = runtimeFromUrl === 'remote' && tenantFromUrl.length > 0;

  const selectedDefinition = useMemo(
    () => definitionItems.find((item) => item.id === selectedDefinitionId),
    [definitionItems, selectedDefinitionId],
  );

  const workflowDefinitions = useMemo(
    () => definitionItems.filter((d) => d.kind === 'Workflow').map((d) => ({ id: d.id, name: d.name })),
    [definitionItems],
  );

  const menuGroups = useMemo(
    () => resolveSidebarMenu(selectedDefinition, metadataDrivenRouterEnabled),
    [selectedDefinition, metadataDrivenRouterEnabled],
  );

  const availableSidebarTabs = useMemo(
    () => new Set(menuGroups.flatMap((group) => group.items.map((item) => item.id))),
    [menuGroups],
  );

  const panelContext = useMemo<PanelAdapterContext>(
    () => ({
      dsl,
      selectedDefinition,
      definitions: definitionItems,
      metadataDrivenRouterEnabled,
    }),
    [dsl, selectedDefinition, definitionItems, metadataDrivenRouterEnabled],
  );

  useEffect(() => {
    if (availableSidebarTabs.has(sidebarTab)) {
      return;
    }
    const defaultTab = resolveDefaultSidebarTab(selectedDefinition, metadataDrivenRouterEnabled);
    setSidebarTab(defaultTab);
  }, [availableSidebarTabs, sidebarTab, selectedDefinition, metadataDrivenRouterEnabled]);

  useEffect(() => {
    if (validationTimeoutRef.current !== null) {
      window.clearTimeout(validationTimeoutRef.current);
    }

    validationTimeoutRef.current = window.setTimeout(async () => {
      setIsLoading(true);
      setEngineError(null);
      try {
        const res = await mpcEngine.parseAndValidate(dsl) as ValidationResult;
        setResult(res);
        const definitions = await mpcEngine.listDefinitions(dsl);
        setDefinitionItems(definitions);
        setSelectedDefinitionId((prev) => {
          if (definitions.some((item) => item.id === prev)) {
            return prev;
          }
          return definitions[0]?.id ?? '';
        });

        if (debugMode && res.status === 'success') {
           // Auto-run a sample eval for now to show trace
           const evalRes = await mpcEngine.evaluateExpr('concat("User: ", data.user)', { data: { user: 'yusuf' } }, true);
           setDebugResult(evalRes);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setEngineError(message);
        setResult(null);
        setDefinitionItems([]);
        setSelectedDefinitionId('');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }, VALIDATION_DEBOUNCE_MS);

    return () => {
      if (validationTimeoutRef.current !== null) {
        window.clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [dsl]);

  useEffect(() => {
    if (!useTenantActiveManifest) return;
    const loadArtifacts = async () => {
      setArtifactsLoading(true);
      setArtifactStatusMessage('');
      try {
        const items = await mpcEngine.listRuleArtifacts(tenantFromUrl);
        setArtifactItems(items);
        const active = items.find((item) => item.status === 'active') ?? items[0];
        if (active) {
          setSelectedArtifactId(active.id);
          setSelectedArtifactStatus(active.status);
        }
      } catch (error) {
        setArtifactStatusMessage(error instanceof Error ? error.message : String(error));
      } finally {
        setArtifactsLoading(false);
      }
    };
    void loadArtifacts();
  }, [tenantFromUrl, useTenantActiveManifest]);

  const handleOpenFolder = async () => {
    try {
      const handle = await window.showDirectoryPicker();
      setFolderHandle(handle);
      const manifestFiles: File[] = [];
      for await (const entry of handle.values()) {
        if (entry.kind === 'file' && (entry.name.endsWith('.manifest') || entry.name.endsWith('.yaml') || entry.name.endsWith('.dsl'))) {
          const file = await (entry as FileSystemFileHandle).getFile();
          manifestFiles.push(file);
        }
      }
      setFiles(manifestFiles);
      if (manifestFiles.length > 0) {
        await handleFileSelect(manifestFiles[0].name, handle);
      }
    } catch (err) {
      console.error('Failed to open folder', err);
    }
  };

  const handleFileSelect = async (
    fileName: string,
    selectedFolderHandle?: FileSystemDirectoryHandle,
  ) => {
    const sourceFolder = selectedFolderHandle ?? folderHandle;
    if (!sourceFolder) return;

    try {
      const handle = await sourceFolder.getFileHandle(fileName);
      setFileHandle(handle);
      const file = await handle.getFile();
      const content = await file.text();
      setDsl(content);
      setActiveFileName(fileName);
    } catch (err) {
      console.error('Failed to select file', err);
    }
  };

  const handleGenerateUISchema = async () => {
    return await mpcEngine.generateUISchema(dsl);
  };

  const handleSimulatePolicy = async (event: any) => {
    return await mpcEngine.evaluatePolicy(dsl, event, {
      tenantId: tenantFromUrl,
      useTenantActiveManifest,
    });
  };

  const handleRedactData = async (data: unknown) => {
    try {
      return await mpcEngine.redactData(dsl, data);
    } catch {
      return { data: redactUnknown(data) };
    }
  };

  const refreshArtifacts = async () => {
    if (!useTenantActiveManifest) return;
    setArtifactsLoading(true);
    setArtifactStatusMessage('');
    try {
      const items = await mpcEngine.listRuleArtifacts(tenantFromUrl);
      setArtifactItems(items);
      if (selectedArtifactId) {
        const selected = items.find((item) => item.id === selectedArtifactId);
        setSelectedArtifactStatus(selected?.status ?? '');
      }
    } catch (error) {
      setArtifactStatusMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setArtifactsLoading(false);
    }
  };

  const loadSelectedArtifact = async () => {
    if (!selectedArtifactId) return;
    setArtifactStatusMessage('');
    try {
      const artifact = await mpcEngine.getRuleArtifact(tenantFromUrl, selectedArtifactId);
      setDsl(artifact.manifest_text);
      setActiveFileName(`artifact:${artifact.id}`);
      setSelectedArtifactStatus(artifact.status);
      setArtifactStatusMessage(`Loaded artifact ${artifact.id}`);
    } catch (error) {
      setArtifactStatusMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const saveDraftArtifact = async () => {
    setArtifactStatusMessage('');
    try {
      if (selectedArtifactId && selectedArtifactStatus === 'draft') {
        const updated = await mpcEngine.updateRuleArtifact({
          tenantId: tenantFromUrl,
          artifactId: selectedArtifactId,
          manifestText: dsl,
        });
        setSelectedArtifactStatus(updated.status);
        setArtifactStatusMessage(`Updated draft ${updated.id}`);
      } else {
        const created = await mpcEngine.createRuleArtifact({
          tenantId: tenantFromUrl,
          manifestText: dsl,
        });
        setSelectedArtifactId(created.id);
        setSelectedArtifactStatus(created.status);
        setArtifactStatusMessage(`Created draft ${created.id}`);
      }
      await refreshArtifacts();
    } catch (error) {
      setArtifactStatusMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const activateSelectedArtifact = async () => {
    if (!selectedArtifactId) return;
    setArtifactStatusMessage('');
    try {
      const activated = await mpcEngine.activateRuleArtifact(tenantFromUrl, selectedArtifactId);
      setSelectedArtifactStatus(activated.status);
      setArtifactStatusMessage(`Activated artifact ${activated.id}`);
      await refreshArtifacts();
    } catch (error) {
      setArtifactStatusMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const handleSave = async () => {
    if (!fileHandle) {
      // Fallback to download or save as if no handle
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: activeFileName,
          types: [{ description: 'Manifest File', accept: { 'text/plain': ['.manifest', '.dsl', '.yaml'] } }]
        });
        setFileHandle(handle);
        setActiveFileName(handle.name);
        const writable = await handle.createWritable();
        await writable.write(dsl);
        await writable.close();
      } catch (err) {
        console.error('Save cancelled or failed', err);
      }
      return;
    }

    setIsSaving(true);
    try {
      const writable = await fileHandle.createWritable();
      await writable.write(dsl);
      await writable.close();
    } catch (err) {
      console.error('Failed to save file', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRun = async () => {
    setIsLoading(true);
    setEngineError(null);
    try {
      const res = await mpcEngine.parseAndValidate(dsl);
      setResult(res as ValidationResult | null);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setEngineError(message);
      setResult(null);
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const validationErrors = result?.errors ?? [];
  const astDefinitions = result?.status === 'success' ? (result.ast?.defs || []) : [];
  const lastWorkerMetrics = mpcEngine.getLastWorkerMetrics();
  const fallbackInspector =
    shouldUseFallbackInspector(selectedDefinition, sidebarTab, metadataDrivenRouterEnabled);
  const selectedWorkflowId = selectedDefinition?.kind === 'Workflow' ? selectedDefinition.id : undefined;

  const renderSidebarPanel = () => {
    if (fallbackInspector) {
      return (
        <DefinitionInspector
          definition={selectedDefinition}
          reason={`'${sidebarTab}' panel is not mapped for kind '${selectedDefinition?.kind}'.`}
        />
      );
    }

    if (sidebarTab === 'editor') {
      return (
        <div className="h-full flex flex-col">
          {useTenantActiveManifest ? (
            <div className="px-3 py-2 border-b border-white/10 bg-white/[0.02] flex flex-wrap items-center gap-2">
              <span className="text-[10px] uppercase tracking-wide text-gray-500">Tenant Artifact</span>
              <select
                aria-label="tenant artifacts"
                title="tenant artifacts"
                value={selectedArtifactId}
                onChange={(event) => {
                  setSelectedArtifactId(event.target.value);
                  const selected = artifactItems.find((item) => item.id === event.target.value);
                  setSelectedArtifactStatus(selected?.status ?? '');
                }}
                className="text-[11px] bg-black/30 border border-white/15 rounded px-2 py-1 text-gray-200 min-w-[220px]"
              >
                <option value="">Select artifact</option>
                {artifactItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id.slice(0, 8)}... | v{item.version} | {item.status}
                  </option>
                ))}
              </select>
              <button type="button" onClick={refreshArtifacts} className="px-2 py-1 text-[10px] rounded bg-slate-700 text-slate-100">
                Refresh
              </button>
              <button type="button" onClick={loadSelectedArtifact} className="px-2 py-1 text-[10px] rounded bg-cyan-700 text-cyan-100" disabled={!selectedArtifactId}>
                Load
              </button>
              <button type="button" onClick={saveDraftArtifact} className="px-2 py-1 text-[10px] rounded bg-violet-700 text-violet-100">
                Save Draft
              </button>
              <button type="button" onClick={activateSelectedArtifact} className="px-2 py-1 text-[10px] rounded bg-emerald-700 text-emerald-100" disabled={!selectedArtifactId}>
                Activate
              </button>
              <span className="text-[10px] text-gray-400">{artifactsLoading ? 'Loading...' : artifactStatusMessage}</span>
            </div>
          ) : null}
          <div className="flex-1 min-h-0">
            <ManifestEditor
              dsl={dsl}
              onChange={setDsl}
              fileName={activeFileName}
              errors={result?.status === 'error' ? (result.errors as any[]) : []}
            />
          </div>
        </div>
      );
    }

    if (sidebarTab === 'registry') {
      return (
        <DomainRegistry
          definitions={astDefinitions}
          onSelectDefinition={(def) => {
            setSelectedDefinitionId(def.id);
          }}
        />
      );
    }
    if (sidebarTab === 'security') {
      return <PolicySimulator onSimulate={handleSimulatePolicy} context={panelContext} />;
    }
    if (sidebarTab === 'redaction') {
      return <RedactionPreview dsl={dsl} onRedact={handleRedactData} />;
    }
    if (sidebarTab === 'acl') {
      return <ACLExplorer dsl={dsl} definitions={definitionItems} context={panelContext} />;
    }
    if (sidebarTab === 'governance') {
      return (
        <GovernancePanel
          namespace={result?.namespace}
          astHash={result?.ast_hash}
          errors={validationErrors}
          definitionCount={astDefinitions.length}
          context={panelContext}
        />
      );
    }
    if (sidebarTab === 'workflow') {
      if (!selectedWorkflowId) {
        return (
          <DefinitionInspector
            definition={selectedDefinition}
            reason="Workflow simulator requires a Workflow definition selection."
          />
        );
      }
      return (
        <WorkflowSimulator
          dsl={dsl}
          workflowId={selectedWorkflowId}
          defaultTenantId={tenantFromUrl}
          useTenantActiveManifest={useTenantActiveManifest}
        />
      );
    }
    if (sidebarTab === 'overlays') {
      return <OverlaySystemPanel dsl={dsl} definitions={definitionItems} context={panelContext} />;
    }
    if (sidebarTab === 'form-preview') {
      const selectedFormId = selectedDefinition?.kind === 'FormDef' ? selectedDefinition.id : '';
      const defaultFormId = selectedFormId || (definitionItems.find((d) => d.kind === 'FormDef')?.id ?? '');
      const formId = formPreviewFormId || defaultFormId;
      if (!formId) {
        return (
          <DefinitionInspector
            definition={selectedDefinition}
            reason="Form preview requires a FormDef definition in the manifest."
          />
        );
      }
      return (
        <FormPreview
          formId={formId}
          workflowOptions={workflowDefinitions}
          workflowId={formPreviewWorkflowId}
          onWorkflowIdChange={setFormPreviewWorkflowId}
          actorId={formPreviewActorId}
          onActorIdChange={setFormPreviewActorId}
          actorRolesInput={formPreviewActorRolesInput}
          onActorRolesInputChange={setFormPreviewActorRolesInput}
          actorAttrsJson={formPreviewActorAttrsJson}
          onActorAttrsJsonChange={setFormPreviewActorAttrsJson}
          onFormIdChange={setFormPreviewFormId}
          onListFormsForState={async (workflowState) => mpcEngine.listFormsForState(dsl, workflowState)}
          onGeneratePackage={async ({ formId: requestedId, data }) =>
            mpcEngine.generateFormPackage({
              dsl,
              formId: requestedId,
              data,
              tenantId: tenantFromUrl,
              useTenantActiveManifest,
              artifactId: selectedArtifactId || undefined,
            })
          }
          onWorkflowStep={async ({ event, currentState, initialState, workflowId, actorId, actorRoles, context }) =>
            mpcEngine.workflowStep({
              dsl,
              workflowId: workflowId || undefined,
              event,
              context: context ?? ({ source: 'form-preview', formId } as any),
              currentState,
              initialState,
              actorId,
              actorRoles,
              tenantId: tenantFromUrl,
              useTenantActiveManifest,
              artifactId: selectedArtifactId || undefined,
              limits: { maxSteps: 100, maxPayloadBytes: 16_384, maxEventNameLength: 128 },
            })
          }
          getLastRuntimeInfo={() => ({
            metrics: mpcEngine.getLastWorkerMetrics(),
            diagnostics: mpcEngine.getLastWorkerDiagnostics(),
          })}
        />
      );
    }
    return (
      <div className="h-full flex items-center justify-center text-gray-500 text-xs italic">
        Feature '{sidebarTab}' coming soon
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#0a0b10] text-[#f3f4f6] font-sans overflow-hidden">
      <Header 
        onOpenFolder={handleOpenFolder} 
        onSave={handleSave} 
        onRun={handleRun} 
        isSaving={isSaving} 
        debugMode={debugMode}
        onToggleDebug={() => setDebugMode(!debugMode)}
      />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar 
          result={result} 
          files={files} 
          activeFile={activeFileName}
          onFileSelect={handleFileSelect}
          activeTab={sidebarTab} 
          onTabChange={setSidebarTab} 
          menuGroups={menuGroups}
        />
        
        <main className="flex-1 flex gap-4 p-4 overflow-hidden">
          <div className="w-[45%] flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative">
              {renderSidebarPanel()}
            </div>
          </div>
          
          <div className="flex-1 flex flex-col gap-4 overflow-hidden">
            <div className="flex-1 glass rounded-2xl overflow-hidden border border-white/10 relative flex flex-col">
              <div className="flex border-b border-white/5 bg-white/[0.02] p-1 gap-1">
                <button 
                  onClick={() => setActiveTab('preview')}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                    activeTab === 'preview' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  Preview
                </button>
                <button 
                  onClick={() => setActiveTab('debug')}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                    activeTab === 'debug' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  Debugger
                </button>
                <button 
                  onClick={() => setActiveTab('ui')}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                    activeTab === 'ui' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  UI Schema
                </button>
                <div className="ml-auto flex items-center gap-2 pr-2">
                  <span className="text-[10px] uppercase tracking-widest text-gray-500">Definition</span>
                  <select
                    aria-label="definition selector"
                    title="definition selector"
                    value={selectedDefinitionId}
                    onChange={(event) => setSelectedDefinitionId(event.target.value)}
                    className="text-[10px] bg-black/30 border border-white/15 rounded px-2 py-1 text-gray-200 min-w-[170px]"
                  >
                    {definitionItems.length === 0 ? <option value="">None</option> : null}
                    {definitionItems.map((item) => (
                      <option key={item.id} value={item.id}>
                        [{item.kind}] {item.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex-1 overflow-hidden">
                {activeTab === 'preview' ? (
                  <Visualizer
                    dsl={dsl}
                    definitionId={selectedDefinitionId || undefined}
                    definitionKind={selectedDefinition?.kind}
                  />
                ) : activeTab === 'debug' ? (
                  <DebugPanel 
                    trace={debugResult?.trace || null} 
                    value={debugResult?.value} 
                    type={debugResult?.type || null}
                  />
                ) : (
                  <UISchemaView onGenerate={handleGenerateUISchema} />
                )}
              </div>
            </div>
            
            <div className="h-48 glass rounded-2xl p-4 border border-white/10 overflow-auto">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Validation Output</h3>
              {engineError ? (
                <div className="text-sm text-red-400 font-mono">[ENGINE_ERROR] {engineError}</div>
              ) : validationErrors.length > 0 ? (
                <div className="space-y-2">
                  {validationErrors.map((err: ValidationError, i: number) => (
                    <div key={i} className="text-sm text-red-400 font-mono">
                      [{err.code}] {err.message}
                    </div>
                  ))}
                </div>
              ) : result?.status === 'success' ? (
                <div className="text-sm text-emerald-400 font-mono">
                  ✓ Semantic & structural validation passed.
                </div>
              ) : (
                <div className="text-sm text-gray-400 font-mono">
                  Validation result pending.
                </div>
              )}
              {lastWorkerMetrics ? (
                <div className="mt-3 text-[10px] text-gray-500 font-mono border-t border-white/5 pt-2">
                  worker:{' '}
                  {lastWorkerMetrics.type} | v{lastWorkerMetrics.contractVersion} |{' '}
                  {lastWorkerMetrics.durationMs ?? 0}ms | diag:{lastWorkerMetrics.diagnosticCount}
                </div>
              ) : null}
            </div>
          </div>
        </main>
      </div>

      <footer className="h-8 glass-card border-t border-white/5 flex items-center px-4 justify-between text-[10px] text-gray-500 uppercase tracking-widest">
        <div className="flex items-center gap-4">
          <span>Engine: Pyodide 0.29.3</span>
          <span>Core: MPC 0.1.0</span>
        </div>
        <div className="flex items-center gap-4">
          <StatusBadge status={isLoading ? 'loading' : engineError ? 'error' : 'ready'} />
          <span>Namespace: {result?.namespace || 'none'}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
