# MPC Studio

MPC Studio is the official visual IDE for the **Manifest Platform Core (MPC) Suite**. It allows developers to author, validate, and visualize manifests directly in the browser.

## Features

- **PWA / Browser-Native**: Runs entirely in the browser using [Pyodide](https://pyodide.org/) for the MPC runtime.
- **Visualizer**: Dynamic graph visualization of state machines and policy flows.
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
```

## Local File System Access

To use the local file system integration:
1. Click **Open Folder** in the header.
2. Grant permission to the browser.
3. Select files from the sidebar workspace.
4. Edit and hit **Save** (Ctrl+S).
