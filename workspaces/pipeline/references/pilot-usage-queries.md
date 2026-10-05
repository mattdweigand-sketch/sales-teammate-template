# Shared usage queries

Warehouse per `policy.pilot_usage.warehouse`, schema `ANALYTICS.ANALYTICS`, read-only.
Substitute `<org_uuid>` from Salesforce, `<window_days>` and `<use_case_sample>` from `policy.pilot_usage`, `<pilot_start>` from the resolved report window,
`<data_through>` as its fixed ISO end date, and `<internal_domain_filter>` with one `user_email NOT ILIKE '%@<domain>'` clause per entry of `policy.tooling.internal_domains`, joined with `AND`.
Dates are cast to text because the connector returns raw day numbers otherwise.

Keep the first-line marker comment on queries 1, 4, and 5 unchanged.
The build helper verifies each explicitly selected submit handle against its marker, org, and fixed report window; markers alone never select results.

## 1. Roster and activity

```sql
-- pilot_usage q1_roster
WITH roster AS (
  SELECT DISTINCT user_id, user_email
  FROM analytics.analytics.dim_organization_user_daily
  WHERE organization_uuid = '<org_uuid>' AND date_pt = '<data_through>' AND is_organization_user
    AND <internal_domain_filter>
),
a AS (
  SELECT user_id, date_pt, daily_query_count, daily_computer_query_count, l7_query_count
  FROM analytics.analytics.dim_user_activity
  WHERE date_pt BETWEEN DATEADD(day, 1 - <window_days>, '<data_through>'::DATE) AND '<data_through>'
    AND user_id IN (SELECT user_id FROM roster)
)
SELECT r.user_email,
       TO_VARCHAR(MIN(CASE WHEN a.daily_query_count > 0 THEN a.date_pt END)) AS first_query,
       TO_VARCHAR(MAX(CASE WHEN a.daily_query_count > 0 THEN a.date_pt END)) AS last_query,
       MAX(CASE WHEN a.date_pt = '<data_through>' THEN a.l7_query_count END) AS l7_queries,
       SUM(a.daily_query_count) AS window_queries,
       SUM(a.daily_computer_query_count) AS window_computer_queries
FROM roster r
LEFT JOIN a ON a.user_id = r.user_id
GROUP BY 1
ORDER BY window_queries DESC NULLS LAST, r.user_email
```

Roster seats as of data-through = row count; this does not verify current provisioning. Active = `window_queries > 0` over `<window_days>`. Active in last 7 days = `l7_queries > 0`. Idle = null or 0.
Computer share here = sum of daily computer queries over sum of daily queries; it is a different definition from the query 2 mode share and the two can disagree.

## 1b. Weekly trend

```sql
WITH roster AS (
  SELECT DISTINCT user_id
  FROM analytics.analytics.dim_organization_user_daily
  WHERE organization_uuid = '<org_uuid>' AND date_pt = '<data_through>' AND is_organization_user
    AND <internal_domain_filter>
)
SELECT TO_VARCHAR(DATE_TRUNC('week', date_pt)) AS week_start,
       COUNT(DISTINCT CASE WHEN daily_query_count > 0 THEN user_id END) AS active_users,
       SUM(daily_query_count) AS queries
FROM analytics.analytics.dim_user_activity
WHERE date_pt BETWEEN DATEADD(day, 1 - <window_days>, '<data_through>'::DATE) AND '<data_through>'
  AND user_id IN (SELECT user_id FROM roster)
GROUP BY 1 ORDER BY 1
```

## 2. Feature mix and models (slow table)

```sql
WITH roster AS (
  SELECT DISTINCT user_id
  FROM analytics.analytics.dim_organization_user_daily
  WHERE organization_uuid = '<org_uuid>' AND date_pt = '<data_through>' AND is_organization_user
    AND <internal_domain_filter>
)
SELECT CASE WHEN GROUPING(product_mode) = 0 THEN 'mode' ELSE 'model' END AS kind,
       COALESCE(product_mode, display_model) AS value,
       COUNT(*) AS queries, COUNT(DISTINCT user_id) AS users
FROM analytics.analytics.fct_queries
WHERE date_pt BETWEEN DATEADD(day, 1 - <window_days>, '<data_through>'::DATE) AND '<data_through>'
  AND user_id IN (SELECT user_id FROM roster)
GROUP BY GROUPING SETS ((product_mode), (display_model))
QUALIFY kind = 'mode' OR ROW_NUMBER() OVER (PARTITION BY kind ORDER BY queries DESC) <= 5
ORDER BY kind DESC, queries DESC
```

`mode` rows are complete, so the mix sums to 100 percent. `model` rows are the top five.
`product_mode` legend: asi = Computer; search_mode = Search; chat_mode = Chat; study_mode, research, research_mode, scheduled_tasks, pro, and NULL roll into Other; display_model is the model.

## 3. Use-case sample (slow table)

```sql
WITH roster AS (
  SELECT DISTINCT user_id, user_email
  FROM analytics.analytics.dim_organization_user_daily
  WHERE organization_uuid = '<org_uuid>' AND date_pt = '<data_through>' AND is_organization_user
    AND <internal_domain_filter>
),
recent AS (
  SELECT q.date_pt, q.query_submitted_at_utc, r.user_id, r.user_email, q.product_mode, q.query_string
  FROM analytics.analytics.fct_queries q
  JOIN roster r ON r.user_id = q.user_id
  WHERE q.date_pt BETWEEN DATEADD(day, 1 - <window_days>, '<data_through>'::DATE) AND '<data_through>'
    AND q.query_string IS NOT NULL
    AND LENGTH(q.query_string) BETWEEN 15 AND 2000
    AND q.query_string NOT LIKE '{%'
  ORDER BY q.date_pt DESC, q.query_submitted_at_utc DESC
  LIMIT 2000
)
SELECT TO_VARCHAR(date_pt) AS day, user_email, product_mode, LEFT(query_string, 120) AS query_text
FROM recent
QUALIFY ROW_NUMBER() OVER (PARTITION BY LEFT(query_string, 60) ORDER BY date_pt DESC) = 1
   AND ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY date_pt DESC, query_submitted_at_utc DESC) <= 8
ORDER BY date_pt DESC
LIMIT <use_case_sample>
```

The `recent` CTE caps the scan at the newest 2000 rows before the window functions run. At most 8 rows per user, so one heavy session cannot fill the sample.
Quote one example per theme verbatim, at the 120-character cut above. Skip file names, JSON, and single words.

## 4. Credit grants (pdf mode, cheap)

```sql
-- pilot_usage q4_grants
SELECT user_email, billing_credit_name, billing_credit_category_enriched,
       TO_VARCHAR(effective_at_pt) AS effective_at, TO_VARCHAR(expires_at_pt) AS expires_at,
       TO_VARCHAR(voided_at_pt) AS voided_at, billing_credit_amount_dollars AS amount_dollars
FROM analytics.analytics.fct_usage_based_billing_credit_grants
WHERE organization_uuid = '<org_uuid>' AND credit_product_type = 'asi'
  AND effective_at_pt::DATE <= '<data_through>'
ORDER BY effective_at_pt
```

One row per effective grant, seat and pool, including voided and expired rows.
`policy.tooling.scripts.pilot_usage_build` keeps rows with `voided_at` null and `effective_at` on or before data-through and converts `amount_dollars` per `policy.pilot_usage.pdf.credit_unit`.
The local build helper's `window` action derives pilot start from the earliest kept `effective_at` before query 5 is submitted.
Grants minus recorded context consumption is not the current available balance.

## 5. Computer tasks with credits (pdf mode, slow table)

```sql
-- pilot_usage q5_tasks
WITH roster AS (
  SELECT DISTINCT user_id, user_email
  FROM analytics.analytics.dim_organization_user_daily
  WHERE organization_uuid = '<org_uuid>' AND date_pt = '<data_through>' AND is_organization_user
    AND <internal_domain_filter>
),
tasks AS (
  SELECT b.context_uuid, b.user_id, MIN(b.date_pt) AS first_date, SUM(b.amount_cents) AS amount_cents
  FROM analytics.analytics.fct_billing_usage_asi b
  WHERE b.date_pt BETWEEN '<pilot_start>' AND '<data_through>'
    AND b.user_id IN (SELECT TO_VARCHAR(user_id) FROM roster)
  GROUP BY 1, 2
),
first_q AS (
  SELECT q.context_uuid, q.query_string
  FROM analytics.analytics.fct_queries q
  WHERE q.date_pt BETWEEN '<pilot_start>' AND '<data_through>'
    AND q.user_id IN (SELECT user_id FROM roster)
    AND q.context_uuid IN (SELECT context_uuid FROM tasks)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY q.context_uuid ORDER BY q.query_submitted_at_utc) = 1
)
SELECT t.context_uuid, r.user_email, TO_VARCHAR(t.first_date) AS first_date,
       TO_VARCHAR(t.amount_cents) AS amount_cents, LEFT(f.query_string, 120) AS task_title
FROM tasks t
JOIN roster r ON TO_VARCHAR(r.user_id) = t.user_id
LEFT JOIN first_q f ON f.context_uuid = t.context_uuid
ORDER BY t.first_date, t.amount_cents DESC
```

One row per billed Computer context (`context_uuid`); `first_date` is its first billing date within the selected window, not necessarily its creation date.
Neither completion nor later return activity is established.
`amount_cents` is the raw billed sum; `policy.tooling.scripts.pilot_usage_build` rounds per `policy.pilot_usage.pdf.credit_display_rule`, then sums. The end date is bound in SQL before aggregation.
`task_title` is the first prompt, 120 characters, for the category review only; it never prints in the PDF. `fct_billing_usage_asi` holds only `asi_*` meter rows, so no meter filter is needed.
