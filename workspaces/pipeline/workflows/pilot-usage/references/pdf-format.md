# Pilot usage PDF

Pages, theme, and fonts per `policy.pilot_usage.pdf`. Page 1 is the numbers (tiles, usage by user, tasks per day, highlights).
Page 2 is what the work was (categories, representative work, interpretation, business value, source note). Every number on both pages is computed by the scripts from queries 1, 4, and 5.
Prose comes only from the approved review file.

## Prerequisites

PDF mode needs prepared Python 3.12 or later with PyYAML and pypdf. Report any unavailable prerequisite before building.
The renderer looks on PATH for `chromium`, `google-chrome`, then `chromium-browser`.
If none is found, it checks `~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome` for Playwright Chromium.
Render copies the licensed bundled fonts from `policy.pilot_usage.pdf.fonts` source paths into the sandbox assets/fonts directory and verifies each policy SHA256.
Print rechecks those font bytes without downloading. Keep the policy fonts, checksums, layout, output paths and approval unchanged.
Page-image inspection needs `pdftoppm` or a PDF page rasterizer such as PyMuPDF, plus an image viewer to inspect both pages before sharing.
Unit tests and helper `--help` do not prove PDF production or visual inspection. Report renderer, font, rasterizer or viewer gaps explicitly.

## Review file

JSON at `<policy.pilot_usage.pdf.output_dir>/review.json`. Draft it, show it, wait for approval.

```
{
  "customer_name": "<Account name as the customer writes it>",
  "organization_uuid": "<from Salesforce>",
  "prepared_by": "<Opportunity Owner.Name from the resolve query>",
  "pilot_end": "<Trial_Expiration_Date__c, ISO; required, the run stops when null>",
  "pilot_start": "<resolved ISO date written by the window action>",
  "data_through": "<fixed ISO date chosen before SQL, required>",
  "confidentiality_label": "<policy.pilot_usage.pdf.confidentiality_label>",
  "approved": false,
  "display_names": {"<email>": "<Contact name>"},
  "participation_notes": {"<email>": "<one line, optional>"},
  "categories": [{"category_id": "<slug>", "label": "<Title case>", "description": "<one sentence>"}],
  "task_categories": {"<context_uuid>": "<category_id>"},
  "narratives": {
    "scope_note": "<one or two sentences>",
    "usage_highlights": [{"label": "<Short label>", "text": "<one sentence>"}],
    "representative_work": [{"title": "<short>", "user_emails": ["<email>"], "summary": "<one or two sentences>"}],
    "work_interpretation": ["<paragraph>", "<paragraph>"],
    "business_value": [{"label": "<Short label>", "text": "<one sentence>"}],
    "source_note": "<one sentence on source and credit unit>"
  }
}
```

Rules. Total categories, including the reserved Uncategorized category, are capped by the length of `policy.pilot_usage.pdf.category_palette`; reserve its last slot.
Check the cap before asking for approval. A task with no entry in `task_categories` lands in `policy.pilot_usage.pdf.uncategorized_category_id`. Four representative work cards.
Two to four work-interpretation paragraphs. Every narrative claim must trace to a task title, a Salesforce field, or a computed number.
Titles indicate attempted work; describe business value as potential unless separate evidence establishes delivery.
Billed contexts do not prove completion, subsequent returns, or a current available credit balance.
No query text, no client or matter names beyond what the task titles already state, no credits or counts typed by hand.

## Approval

Save the full task-title list, grouped by category, to a sandbox file before asking for approval. Never list every title in chat.
Show in chat, numbered. 1 categories, each with its task count. 2 display names and participation notes. 3 narratives. Wait. Edit the file on corrections.
Set `approved: true` only on approval. The pipeline refuses an unapproved file.

## Pipeline

Run from the Project Files checkout. `<dir>` is `policy.pilot_usage.pdf.output_dir`; `<tool_calls>` is this session's saved tool-call directory. Keep the exact handles returned by the three submits.

After query 4 completes, with org, pilot end and data-through in the draft review:

```
<policy.tooling.scripts.pilot_usage_build> window --review <dir>/review.json --tool-calls <tool_calls> --grants-handle <q4_handle>
```

This fills pilot_start and resets approval to false. Query 5 must then use these exact dates. After categories, names and narratives receive approval, build with JSON Boolean `true` (never a string):

```
<policy.tooling.scripts.pilot_usage_build> build --review <dir>/review.json --tool-calls <tool_calls> --roster-handle <q1_handle> --grants-handle <q4_handle> --tasks-handle <q5_handle> --output <dir>/<account-slug>-pilot-usage.pdf
```

The build checks the selected submits' markers, org, dates and complete terminal results. It writes local input/report JSON and HTML beside the PDF.
Render recomputes and validates; print verifies fonts, page count and size before replacing the PDF.
The review flag records the user's approval; the helper cannot independently prove a chat approval occurred. Inspect both page images before sharing.
