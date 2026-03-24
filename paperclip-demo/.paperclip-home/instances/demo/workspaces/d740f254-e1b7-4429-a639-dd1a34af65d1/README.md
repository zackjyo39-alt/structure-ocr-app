# MVP Vertical Slice

Single-user todo workflow proving an end-to-end slice with CI quality gates.

## Run

```bash
npm install
npm run ci
npm run dev
```

Open http://localhost:3000.

## Scope mapping

- Versioned API: `/api/v1/todos`
- Validation: `zod` request schema
- Minimal observability: structured startup log + `/health`
- CI gates: lint, tests, build, smoke in `.github/workflows/ci.yml`
