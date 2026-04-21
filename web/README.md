# AML Guard — Demo Frontend

Next.js 14 + TypeScript + Tailwind. Mock-first demo UI for the AML Guard agent. See the full plan in Obsidian: `MTX UC1 - AML Guard Frontend`.

## Run

```bash
npm install
npm run dev
# http://localhost:3001 → redirects to /investigate
```

If `npm install` errors due to the global `ignore-scripts=true`:

```bash
npm install --ignore-scripts=false
```

## Switch from mocks to live backend

Set the base URL when the teammate's API is ready:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

The frontend calls `POST {NEXT_PUBLIC_API_BASE}/api/investigate` with a `{ question }` body and expects a `CaseAssessment` (see `lib/types.ts`).

## Demo path

1. Open `/investigate`.
2. Click the **"Investigate Nielsen Enterprises Limited"** preset chip.
3. Watch tool steps stream in → HIGH_RISK verdict + gauge → findings + typology evidence → audit timeline → subgraph.
