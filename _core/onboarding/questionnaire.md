# Onboarding questionnaire

Ask the remaining persistent company questions together, then walk every integration in adapters.md and integrations.json. Reuse existing answers.
Per-run Account names, deals, events and evidence belong at task entry.

Collect actual company settings. Required questions have no fictional defaults. No credentials or customer evidence belong in the answer file.

| Answer | Question | Canonical target |
|---|---|---|
| `company_name` | Company name? | template.company_name |
| `owner_name` | Sales operator display name? | template.owner_name |
| `owner_email` | Sales operator email? | prospecting.identity.owner_email, momentum.attendee_email |
| `owner_id` | Verified Salesforce User ID? | prospecting.identity.sfdc_user_id |
| `timezone` | Local IANA timezone? | prospecting.identity.timezone, momentum.display_tz |
| `internal_domains` | Internal email domains as a JSON list? | tooling.internal_domains |
| `crm_url` | Salesforce HTTPS origin? | salesforce.instance_url |
| `note_initials` | Note initials? | Derived note patterns, greeting or setup state |
| `product_name` | Product name? | template.product_name |
| `product_value` | One supported value statement? | template.product_value |
| `product_evidence` | Approved product sources and claim limits? | template.product_evidence |
| `product_review_date` | Product evidence review date, ISO? | template.product_review_date |
| `icp` | Territory, industries, personas and exclusions? | template.icp |
| `quarter_targets` | Quarter targets as a JSON map? | forecast.targets |
| `quarter_target_default` | Default quarterly target? | forecast.target_default |
| `amount_field` | CRM revenue field API name? | forecast.amount_field |
| `warehouse` | Read-only warehouse name when Warehouse is selected? | pilot_usage.warehouse, prospecting.warehouse.name |
| `warehouse_timezone` | Timezone used by warehouse dates when Warehouse is selected? | template.warehouse_timezone |
| `ops_channel` | Actual operations channel ID when Slack is selected? | close.ops_channel |
| `ops_owners` | Actual operations user IDs as JSON list when Slack is selected? | close.ops_owners |
| `deal_desk_channel` | Actual deal desk channel ID when Slack is selected? | close.deal_desk_channel |
| `artifact_dir` | Absolute external directory for run artifacts? | pilot_usage.pdf.output_dir |
| `crm_field_map` | CRM sample-to-actual API names as a JSON map? | Mapped API names in policy, scripts and references |
| `warehouse_table_map` | Warehouse sample-to-actual table names as JSON map? | Mapped API names in policy, scripts and references |

| `integration_setup` | Explicit configuration choice and non-secret settings for all 21 integrations? | template.integrations and named setting targets |

Warehouse and Slack routing answers may be omitted when their integration is deferred or unused.
Review every system anyway and record a concrete reason. The selected workflow still needs its required capabilities before live use.

The CLI schema is `questions.json`. Full field and table names are in `adapter-schema.json`. The agent saves the collected answers outside both workspace folders.
Validate all values, instantiate at an absent separate destination, then run check. Setup does not create agents, grant permissions or activate schedules.

For each integration, explain its setup, authentication and checks from integrations.json. Capture connection metadata only.
Guide actual OAuth, MCP and API-key setup in the runtime connection screen or secret store, with no secret values in the answer file.
See adapters.md for the answer shape, complete checklist and deployment sequence.
