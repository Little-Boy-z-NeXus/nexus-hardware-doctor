# nexus-frontend

React + Vite shell for the NeXus hackathon MVP. It owns three routes:

- `/dashboard` — overall health, live telemetry and preventive risk
- `/hardware` — fixed ESP32 → INA219 → L298N → DC motor topology
- `/doctor` — natural-language diagnosis and safety context

## Development setup

```bash
npm ci
npm run dev
```

Copy `.env.example` to `.env.local` only when you need to override the local defaults. All browser-exposed variables must use the `VITE_` prefix; never put secrets in frontend environment files.

## Quality gate

```bash
npm run check
```

This runs ESLint and the production TypeScript/Vite build. Do not add authentication, billing, multi-tenant navigation, or a drag-and-drop circuit editor during the MVP.
