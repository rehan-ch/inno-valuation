# InnoValuation frontend

Next.js (App Router), TypeScript, Tailwind. Node 20.19 or newer.

## Commands

- `npm run dev`: start the dev server on http://localhost:3000
- `npm run build` / `npm start`: production build and server
- `npm run lint`: ESLint
- `npm run typecheck`: generate Next route types, then `tsc --noEmit`
- `npm test`: Vitest + Testing Library

## API

The client in `src/lib/api/client.ts` calls `${NEXT_PUBLIC_API_BASE_URL}/api/v1`
(default `http://localhost:8000`) with cookies included. The variable is defined in
the root `.env.example`. `NEXT_PUBLIC_*` values are inlined at build time.

See the root `README.md` and `docs/` for project rules.
