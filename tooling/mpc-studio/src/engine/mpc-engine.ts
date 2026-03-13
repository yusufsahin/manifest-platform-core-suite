export class MPCEngine {
  private worker: Worker;
  private pendingRequests: Map<string, { resolve: (value: unknown) => void; reject: (reason?: unknown) => void }> = new Map();

  constructor() {
    this.worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    this.worker.onmessage = this.handleMessage.bind(this);
  }

  private handleMessage(e: MessageEvent) {
    const { id, type, payload } = e.data;
    const request = this.pendingRequests.get(id);
    
    if (request) {
      if (type === 'ERROR') {
        request.reject(payload);
      } else {
        request.resolve(payload);
      }
      this.pendingRequests.delete(id);
    }
  }

  private postMessage<T>(message: { type: string; payload: any }): Promise<T> {
    const id = Math.random().toString(36).substring(7);
    return new Promise<T>((resolve, reject) => {
      this.pendingRequests.set(id, { 
        resolve: (val: any) => resolve(val as T), 
        reject 
      });
      this.worker.postMessage({ id, ...message });
    });
  }

  async parseAndValidate(dsl: string): Promise<unknown> {
    return this.postMessage<unknown>({ type: 'PARSE_AND_VALIDATE', payload: dsl });
  }

  async getMermaid(dsl: string): Promise<string> {
    return this.postMessage<string>({ type: 'MERMAID_EXPORT', payload: dsl });
  }

  async evaluateExpr(expr: string, context?: any, enableTrace: boolean = false): Promise<any> {
    return this.postMessage<any>({ 
      type: 'EVALUATE_EXPR', 
      payload: { expr, context, enable_trace: enableTrace } 
    });
  }

  async evaluatePolicy(dsl: string, event: any): Promise<any> {
    return this.postMessage<any>({
      type: 'EVALUATE_POLICY',
      payload: { dsl, event }
    });
  }

  async generateUISchema(dsl: string): Promise<any> {
    return this.postMessage<any>({
      type: 'GENERATE_UISCHEMA',
      payload: { dsl }
    });
  }
}

export const mpcEngine = new MPCEngine();
