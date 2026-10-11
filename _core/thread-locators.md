# Teammate thread destinations

## Teammate thread lookup

Read current runtime destinations or run `pplx tm orchestrator list` for the owning teammate.
Use the unique approved role entry's `agent_id` as the owning session context UUID. Never choose by a title search alone.
The roster is not a complete deal-thread inventory. Do not use it to prove a deal thread absent or unique.
Use `session_get` to verify the destination's project against the current runtime project before reading history or routing output.
An explicit approved runtime UUID or URL can supply a missing roster destination. Conflicting or unreadable destinations stay not checked.
Prefer `load_sessions` in Code Mode with that context UUID, never a URL task ID.
Read its `memory/sessions/<week>/<short_id>/conversation.md`, including `first_entry_at`, `last_entry_at` and the UTC entry headings.
If it is unavailable or fails, fall back to `session_download_content` into its own sandbox directory. Metadata previews never replace a transcript.
Apply the consuming contract's timestamp-coverage checks. A successful load can still omit older entries, and an undated export cannot prove a timed window complete.
Missing history is not proof of a first report or no change. Follow the consuming contract's evidence limits without inventing prior content.
