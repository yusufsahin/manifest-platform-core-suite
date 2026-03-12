export class MPCEngine {
  private worker: Worker;
  private pendingRequests: Map<string, { resolve: Function, reject: Function }> = new Map();

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

  async parseAndValidate(dsl: string): Promise<any> {
    const id = Math.random().toString(36).substring(7);
    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.worker.postMessage({ id, type: 'PARSE_AND_VALIDATE', payload: dsl });
    });
  }
}

export const mpcEngine = new MPCEngine();
