# Contributing

Thanks for helping improve Fanbook. This project is currently optimized for a
single-team private deployment workflow, so contributions should preserve that
scope unless a broader product direction is explicitly discussed first.

## Development Setup

Backend:

```bash
cd backend
mvn test
```

Frontend:

```bash
cd frontend
npm install
npm test
npm run typecheck
npm run build
```

For a local UI preview without the Java backend, run the mock API and Vite dev
server in separate terminals:

```bash
cd frontend
npm run mock-api
```

```bash
cd frontend
npm run dev
```

README screenshots are generated from the real Vite app and mock API:

```bash
cd frontend
npm run screenshots:readme
```

If Playwright cannot find a Chromium browser on a fresh machine, install the
browser cache first:

```bash
cd frontend
npm run screenshots:install-browser
```

## Contribution Guidelines

- Keep secrets out of Git. Use `backend/.env.example` as a template and keep
  real `.env` files local.
- Do not commit uploaded EPUBs, generated exports, runtime storage, database
  dumps, logs, browser profiles, or local agent/tooling directories.
- Use mock data for tests and screenshots unless sample content is explicitly
  licensed for redistribution.
- Keep backend changes aligned with the package boundaries under
  `backend/src/main/java/com/fanbook/`.
- Keep frontend API DTOs and rendering behavior aligned with
  `frontend/src/types.ts` and `frontend/src/api/client.ts`.
- Run the relevant backend and frontend checks before submitting a change.

## Pull Request Checklist

- [ ] The change is scoped to the issue or feature being addressed.
- [ ] Tests were added or updated when behavior changed.
- [ ] Backend tests pass with `mvn test` when backend code changed.
- [ ] Frontend tests, typecheck, and build pass when frontend code changed.
- [ ] No real credentials, private EPUBs, generated artifacts, or local runtime
      files are included.
- [ ] New dependencies are compatible with the repository license and are noted
      in `THIRD_PARTY_NOTICES.md` when needed.
