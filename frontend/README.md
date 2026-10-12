# InnoValuation frontend

Next.js (App Router), TypeScript, Tailwind. Node 20.19 or newer.

## Commands

- `npm run dev`: start the dev server on http://localhost:3000
- `npm run build` / `npm start`: production build and server
- `npm run lint`: ESLint
- `npm run typecheck`: generate Next route types, then `tsc --noEmit`
- `npm test`: Vitest + Testing Library
- `npm run gen:api`: generate `src/lib/api/schema.d.ts` from `openapi.json`
- `npm run check:api`: fail if `schema.d.ts` does not match `openapi.json`

## API

The client in `src/lib/api/client.ts` calls `${NEXT_PUBLIC_API_BASE_URL}/api/v1`
(default `http://localhost:8000`) with cookies included. The variable is defined in
the root `.env.example`. `NEXT_PUBLIC_*` values are inlined at build time.

API types are generated, not hand-written. `openapi.json` is the backend's OpenAPI
schema (`uv run python -m app.openapi_dump > ../frontend/openapi.json` in `backend/`),
and `npm run gen:api` turns it into `src/lib/api/schema.d.ts`. Import types through
`src/lib/api/types.ts`. CI fails if either file is stale.

See the root `CLAUDE.md` for project rules.
