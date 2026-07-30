# Frontend Progress

Last updated: 2026-07-30

## Current state

- Frontend React/Vite exists in `frontend/`.
- Docker UI build uses Node build stage and Nginx runtime.
- UI Nginx proxies `/api` and `/health` to the API container.
- Sidebar document selection sends `document_scope="selected"` plus the selected document IDs.
- If the user deselects every document, the UI warns them and the backend does not search the full corpus.

## Verified

- `npm run build` passes with the current document filter contract.
- Dockerfile UI has a production static serving path.

## Open work

- Run full browser verification for chat/upload/citation images.
- Use the `impeccable` skill if the UI needs a deeper polish pass.
- Decide final internal domain/reverse proxy if removing direct port `8501`.
