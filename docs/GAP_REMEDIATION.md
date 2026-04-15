# Gap Remediation (Audit Findings → Fixes)

Bu doküman, `manifest-platform-core-suite` üzerinde yapılan codebase-wide gap audit çıktılarını ve uygulanan düzeltmeleri kalıcı olarak kayıt altına alır.

## Doğrulama Checklist’i (son durum)

- `mpc-conformance run packages/core-conformance/fixtures/` → **PASS** (66/66)
- `python -m pytest tests/ -q` → **PASS** (530 tests)
- `mpc validate examples/getting_started.manifest` → **PASS** (`examples/getting_started.py` bir Python örneği; DSL bloğu `examples/getting_started.manifest` olarak ayrıldı)
- `tooling/mpc-studio/npm run test:ci` → **PASS**
- **Not (Windows)**: `mpc validate` başarı çıktısında Unicode onay işareti kullanımı bazı Windows konsollarında `charmap` encode hatasına yol açabildiği için mesaj ASCII **`OK: Validation passed.`** olarak güncellendi.
- **Not (Git hygiene)**: `tooling/mpc-studio/playwright-report/` ve `tooling/mpc-studio/test-results/` üretim çıktıları repodan takipten çıkarıldı (Studio `.gitignore` zaten ignore ediyor).

## Grup 1 — Kritik (Doğruluk / Bütünlük)

### 1) Sahte KMS imzalama kaldırıldı

- **Dosya**: `src/mpc/enterprise/governance/kms.py`
- **Sorun**: `AWSKMSSigningPort.sign()` SHA-256 digest’i base64’e çevirip “imza” gibi dönüyordu (gerçek KMS imzası değil).
- **Fix**: `sign()` artık açık şekilde **`NotImplementedError`** fırlatıyor ve gerçek boto3/KMS entegrasyonu talep ediyor.
- **Test**: `tests/test_governance_kms.py` güncellendi; `sign()` için `NotImplementedError` bekleniyor.

### 2) Activation audit exception yutma kaldırıldı

- **Dosya**: `src/mpc/enterprise/governance/activation.py`
- **Sorun**: Audit aşamasında `except Exception: pass` ile hata sessizce kayboluyordu.
- **Fix**: exception artık `errors.append(Error(code="E_GOV_ACTIVATION_FAILED", severity="warn", ...))` ile raporlanıyor.

### 3) CLI validate hardcoded demo meta kaldırıldı + `--meta` eklendi

- **Dosya**: `src/mpc/tooling/cli.py`
- **Sorun**: `validate` komutu drift detection için hardcoded `demo_meta` kullanıyordu; gerçek manifestlerde yanlış/eksik çıktı üretiyordu.
- **Fix**:
  - `mpc validate <file> --meta <meta.json>` desteklendi.
  - `--meta` yoksa structural meta AST’den **permissive** derive ediliyor.
  - Drift detection yalnızca `--meta` ile çalışıyor.
- **Ek fix**: `resolve-imports` içindeki sessiz parse hatası uyarıya çevrildi.

### 4) Workflow history restore `pass` yerine intent açıklaması

- **Dosya**: `src/mpc/features/workflow/fsm.py`
- **Sorun**: History restore içinde `pass` bırakılmıştı.
- **Fix**: “history leaf states zaten aktif leaf’lerdir” açıklaması eklendi.

## Grup 2 — Orta (Test Kapsamı / Tamamlanmamışlık)

### 1) `mpc-conformance` yerel kodu kullanacak şekilde hizalandı

- **Sorun**: `mpc-conformance` bazı ortamlarda site-packages içindeki eski runner’ı kullanabiliyordu.
- **Fix**: Repo editable install ile doğrulandı: `python -m pip install -e .`

### 2) Yeni conformance kategorileri eklendi

- **Routing**: `packages/core-conformance/fixtures/routing/*`
- **Redaction**: `packages/core-conformance/fixtures/redaction/*`
- **Imports**: `packages/core-conformance/fixtures/imports/*`
- **Runner**: `src/mpc/tooling/conformance/runner.py` handler’ları eklendi.

### 3) Eksik fixture setleri tamamlandı

- **Imports**: cycle detection, semver constraint fail
- **Redaction**: nested redaction
- **ACL**: role hierarchy expansion, priority ordering deny>allow, ABAC deny
- **Workflow**: actions (enter/leave + transition), shallow history, timeout transition

## Grup 3 — Düşük (UX / DX)

### 1) Domain Registry arama + detail wiring

- **Dosya**: `tooling/mpc-studio/src/components/DomainRegistry.tsx`, `tooling/mpc-studio/src/App.tsx`
- **Fix**:
  - Search input state + filtreleme eklendi.
  - “Detail” butonu `onSelectDefinition` ile `selectedDefinitionId` set ediyor.

### 2) Pyodide CDN configurable

- **Dosya**: `tooling/mpc-studio/src/engine/worker.ts`, `tooling/mpc-studio/.env.example`
- **Fix**: `VITE_PYODIDE_CDN_URL` ile `loadPyodide({ indexURL })` override edilebilir.

### 3) Phase test dosyaları / placeholder temizlik

- **Dosya**: `tests/test_dummy.py`
- **Fix**: Placeholder test kaldırıldı.
- **Not**: Phase test dosyalarındaki `__main__` blokları kaldırıldı (pytest dışı çalışma yüzeyi azaltıldı).

## Ek Notlar

- Studio lint: `eslint.config.js` altında `test-results/` ve `playwright-report/` ignore edildi (E2E sonrası ESLint scandir hatalarını önler).

