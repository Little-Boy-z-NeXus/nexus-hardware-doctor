# nexus-frontend

The frontend is a React, TypeScript and Vite application for the NeXus hackathon MVP. It provides the Dashboard, Hardware Graph, and AI Doctor shell in one responsive interface.

## Current MVP state

Available now:

- responsive desktop/mobile application shell
- React Router navigation for all three screens
- typed v1 contract mirrors
- Vite environment configuration
- ESLint and production build checks

The visible readings and conversation are presentation data for G01. Real/mock API switching, WebSocket reconnect, and runtime schema-error states belong to backlog item G02.

## Prerequisites

On Windows, no terminal commands are required: double-click `nexus-start-frontend.cmd` in the repository root. The launcher installs missing packages automatically. Use `nexus-start-app.cmd` to start both frontend and backend and open the dashboard.

- Node.js 22 LTS
- npm included with Node.js
- A cloned `nexus-hardware-doctor` repository

Confirm versions:

```bash
node --version
npm --version
```

## Install and run from the repository root

### Windows PowerShell

```powershell
npm --prefix frontend ci
Copy-Item frontend\.env.example frontend\.env.local
npm --prefix frontend run dev
```

### macOS or Linux

```bash
npm --prefix frontend ci
cp frontend/.env.example frontend/.env.local
npm --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. Vite prints the actual URL if the default port is unavailable.

## Install and run from inside `frontend`

```bash
cd frontend
npm ci
npm run dev
```

Copy `.env.example` to `.env.local` only when you need to override the defaults.

## Routes

| Route | MVP purpose |
| --- | --- |
| `/dashboard` | Overall health, live signal cards, preventive risk and activity |
| `/hardware` | Fixed ESP32 → INA219 → L298N → DC motor topology |
| `/doctor` | Natural-language diagnosis, evidence and safety context |

Unknown paths redirect to `/dashboard`.

## Environment variables

Template: [`.env.example`](.env.example)

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend HTTP base URL |
| `VITE_DEVICE_ID` | `nexus-demo-esp32` | Device selected by the MVP UI |

Every browser-exposed variable must use the `VITE_` prefix. Never put Nebius keys, device secrets, Wi-Fi passwords, or private tokens in a frontend environment file because Vite bundles exposed values into client code.

Restart the development server after changing `.env.local`.

## Available commands

Run these inside `frontend`, or prefix them with `npm --prefix frontend` from the repository root.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the local Vite development server |
| `npm run lint` | Run ESLint over TypeScript and React code |
| `npm run test` | Run all Vitest unit tests once |
| `npm run test:watch` | Re-run affected unit tests while developing |
| `npm run build` | Type-check and create the production bundle in `dist/` |
| `npm run check` | Run lint, unit tests, and the production build |
| `npm run preview` | Serve the built `dist/` bundle locally |

## Quality check

```bash
npm run check
```

Expected result: ESLint exits without errors, nine unit tests pass, and Vite creates `dist/index.html` plus hashed assets. `dist/` and `node_modules/` are generated locally and must not be committed.

Run only the unit tests or keep them in watch mode:

```bash
npm run test
npm run test:watch
```

Route tests use Testing Library with an in-memory router; configuration tests exercise URL normalization without contacting a live backend. Protocol-level availability and latency belong to [`../nexus-k6-tests`](../nexus-k6-tests/README.md).

Test the production bundle:

```bash
npm run build
npm run preview
```

## Source structure

```text
frontend/
├── .env.example
├── eslint.config.js
├── index.html
├── package.json
├── tsconfig.json
├── vitest.config.ts
└── src/
    ├── components/    Shared application shell and page header
    ├── config/        Validated/defaulted environment access
    ├── contracts/     TypeScript mirrors of contract v1
    ├── pages/         Dashboard, Hardware Graph and AI Doctor routes
    ├── test/          Shared Vitest setup
    ├── App.tsx        Route definitions
    ├── App.test.tsx   Route and navigation unit tests
    ├── main.tsx       Browser entry point
    └── styles.css     Responsive MVP design system and page styles
```

The canonical schemas are under [`../nexus-contracts/v1`](../nexus-contracts/v1/README.md). Keep payload keys in `snake_case`; map to presentation labels only at the UI boundary.

## Adding frontend code

- Put route-level screens in `src/pages`.
- Put reusable UI in `src/components`.
- Read environment variables only through `src/config/env.ts`.
- Put shared transport types in `src/contracts`; do not duplicate field names inside pages.
- Keep components accessible with labels, semantic elements, keyboard behavior, and visible focus states.
- Keep the MVP usable at 500 px and 1440 px viewport widths.
- Do not add authentication, billing, multi-tenant navigation, or a drag-and-drop circuit editor during the MVP.

## Common problems

- `npm ci` reports an engine/version issue: install Node.js 22 LTS and retry.
- `npm ci` reports lockfile mismatch: do not edit the lockfile manually; run `npm install` only when intentionally changing dependencies and commit both package files.
- Blank page on a direct production route: configure the host to fall back to `index.html` for client-side routes.
- Frontend cannot reach backend: confirm the backend health endpoint, `VITE_API_BASE_URL`, browser console, and CORS configuration.
- Environment change is ignored: restart Vite after editing `.env.local`.
- Port 5173 is busy: Vite prints another local port; use that URL or stop the existing process.
