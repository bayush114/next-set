# Next Set
A minimal workout tracker with a real account-scoped backend, offline queue, reusable routines, explainable progression suggestions, and progress charts.

## Features
- Prefilled sets and one-tap completion, with editable weights and reps.
- Saved routines plus optional Push/Pull/Legs starting templates.
- Immutable session history and repeat-with-suggestions actions.
- Configurable target reps and weight increments. Suggestions require every planned set to be completed at target, at a consistent weight. Nothing is increased automatically.
- Body-weight, daily training-volume, and exercise-weight charts with accessible value tables.
- ChatGPT sign-in, D1 persistence, per-user authorization, and account-specific IndexedDB storage.
- Offline application shell and queued writes, retried while the app is open and connected.
- JSON import/export and explicit migration of original `next-set-v1` localStorage data.

## Stack
React, TypeScript, Vinext/Vite, Cloudflare Workers, D1/SQLite, Drizzle migrations, IndexedDB, and a service worker. Hosted authentication is supplied by Sites; authentication secrets are not stored in this repository.

## Local development
Use Node 22.13+ (Node 24 for the included SQLite tests) and pnpm.

1. `pnpm install --frozen-lockfile`
2. `pnpm build`
3. Apply `drizzle/0000_chilly_tag.sql` locally using the command below.
4. `pnpm dev`

```
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_chilly_tag.sql
```

Managed preview uses platform auth; without a signed-in identity, the UI works in local mode. Portable loopback development can use the starter's development sign-in. Never trust user-supplied identity headers on a publicly exposed standalone server; production depends on Sites validating and injecting them.

## Validation
- `node node_modules/typescript/bin/tsc --noEmit`
- `node scripts/test.mjs`
- `pnpm build`

Tests exercise validation, progression edge cases, immutable merging, SQLite-backed idempotency, pagination, cross-origin rejection and per-user isolation.

## Sync design
The local IndexedDB transaction adds immutable records and outbox IDs together. The server uses a unique `(user_id, record_id)` index. Retrying an accepted upload is safe. Pulls use a sequence cursor, scoped to the authenticated account. Saving a revised routine creates another template rather than overwriting other devices' versions. Unfinished workouts remain device-local. Sync checks account identity before uploading; switching accounts never merges data silently.

## Limits
Cloud sync requires sign-in and connectivity. Automatic retries run while the app is open, not as guaranteed OS background tasks. Offline reopening requires a successful online load and service-worker activation. Clearing browser storage removes unuploaded data. Local-mode logs are separate from signed-in records; use export/import to move them. Charts use UTC dates for aggregation. This version does not include history deletion or editing, kg units, or automatic conflict resolution for editable sessions because saved sessions are immutable.

## Privacy and deployment
API responses are never cached by the service worker. Cached HTML contains no account identity or workout data; device records live in account-specific IndexedDB buckets. Signing out removes the remembered offline account pointer. The hosted Site remains owner-private until explicitly shared. `.openai/hosting.json` declares the Site identity and D1 binding and contains no secret.
