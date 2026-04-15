# MPC Runtime (minimal FastAPI)

Bu klasör, `mpc-studio` için **minimal remote runtime** sağlar (MVP).

## Amaç

- Studio `VITE_MPC_RUNTIME_MODE=remote` iken çalışacak şekilde:
  - `POST /api/v1/rule-artifacts/runtime/forms/package`
  - Minimal artifact lifecycle: create/list/get/activate
- Hata formatı: `{ "code": "...", "message": "...", "retryable": false }`

## Çalıştırma

Önce bağımlılıklar:

```bash
python -m pip install -r tooling/mpc-runtime/requirements.txt
```

Sonra server:

```bash
set PYTHONPATH=src
python -m uvicorn tooling.mpc_runtime.app:app --reload --port 8787
```

Studio env:

```bash
set VITE_MPC_RUNTIME_MODE=remote
set VITE_MPC_RUNTIME_BASE_URL=http://localhost:8787/api/v1/rule-artifacts
```

## Notlar

- Artifact store **in-memory**’dir (kalıcılık yok).
- AuthZ/Multi-tenant enforcement MVP seviyesinde “shape” ve error-code uyumu odaklıdır.

