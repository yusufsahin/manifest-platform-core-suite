# MPC Studio

MPC Studio is the official visual IDE for the **Manifest Platform Core (MPC) Suite**. It allows developers to author, validate, and visualize manifests directly in the browser.

## Features

- **PWA / Browser-Native**: Runs entirely in the browser using [Pyodide](https://pyodide.org/) for the MPC runtime.
- **Visualizer**: Dynamic graph visualization of state machines and policy flows.
- **Workflow Simulator**: Dedicated step-by-step state transition simulation (`step/run/back/reset/export`) with trace timeline.
- **Monaco Editor**: Rich code editing with MPC DSL support.
- **Local File System Access**: Direct integration with your local disk via the [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API).
    - Open local folders and browse manifest files.
    - Save changes directly back to your local files.
    - Idempotent "Save as" fallback for non-supported browsers.

## Tech Stack

- **Framework**: React + Vite
- **Language**: TypeScript
- **Runtime**: Pyodide (MPC Python Core)
- **UI**: Tailwind CSS + Lucide Icons + Framer Motion
- **Editor**: Monaco Editor

## Development

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Run fixture quality gate (workflow + contracts + validator + integration)
npm run test:conformance

# CI-equivalent local run
npm run test:ci

# Benchmark run (prints p50/p95)
npm run test:benchmark

# Benchmark run with threshold enforcement
npm run test:benchmark:enforce
```

## Operational Flags

- `VITE_WORKFLOW_TRACE_V2=false`: emergency kill switch for trace v2 UI (falls back to legacy trace mode).

## Local File System Access

To use the local file system integration:
1. Click **Open Folder** in the header.
2. Grant permission to the browser.
3. Select files from the sidebar workspace.
4. Edit and hit **Save** (Ctrl+S).
