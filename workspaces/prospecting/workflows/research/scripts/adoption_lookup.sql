-- signal-user-scan. One row of org-level adoption facts for one Salesforce Account.
-- Bindings, 1-based: ?1 Salesforce Account Id (18 char), ?2 account email domain (lowercase, no @), ?3 date_pt (today minus policy warehouse.data_lag_days, YYYY-MM-DD).
-- Returns 7 of the 11 policy user_scan.bundle_keys. The stage adds account_name, salesforce_account_id, account_domain, and derives adoption.
-- org_service_types and org_platforms are comma-joined strings. Empty string means none, the stage splits to an empty list.
-- Counts only organizations with is_deleted = FALSE, the same set the booleans read.
-- Returns booleans and categories only. Never add user ids, emails, names, counts of people, or activity timestamps.
WITH acct AS (
  SELECT ? AS salesforce_account_id, LOWER(?) AS domain, TO_DATE(?) AS date_pt
),
org_map AS (
  SELECT i.organization_uuid, o.service_type
  FROM analytics.analytics.int_organization_salesforce_identity i
  JOIN analytics.analytics.dim_organizations o
    ON o.organization_uuid = i.organization_uuid AND o.is_deleted = FALSE
  JOIN acct ON i.salesforce_account_id = acct.salesforce_account_id
  WHERE i.is_identity_unambiguous
),
org_sub AS (
  SELECT s.organization_uuid, m.service_type, s.is_subscribed, s.is_paying, s.subscription_platform
  FROM analytics.analytics.dim_organization_subscription_daily s
  JOIN org_map m ON m.organization_uuid = s.organization_uuid
  JOIN acct ON s.date_pt = acct.date_pt
),
individuals AS (
  SELECT COUNT(*) > 0 AS paid_individuals_exist
  FROM analytics.analytics.dim_subscription_user_daily d
  JOIN analytics.analytics.dim_user_attributes u ON u.user_id = d.user_id
  JOIN acct ON d.date_pt = acct.date_pt AND LOWER(u.email_domain) = acct.domain
  WHERE d.is_paying = TRUE
)
SELECT
  (SELECT TO_CHAR(date_pt, 'YYYY-MM-DD') FROM acct)                  AS data_through_date,
  (SELECT COUNT(*) FROM org_map)                                     AS mapped_org_count,
  COALESCE((SELECT BOOLOR_AGG(is_subscribed) FROM org_sub), FALSE)   AS org_subscribed,
  COALESCE((SELECT BOOLOR_AGG(is_paying) FROM org_sub), FALSE)       AS org_paying,
  COALESCE((SELECT LISTAGG(DISTINCT service_type, ',') FROM org_sub), '')          AS org_service_types,
  COALESCE((SELECT LISTAGG(DISTINCT subscription_platform, ',') FROM org_sub), '') AS org_platforms,
  (SELECT paid_individuals_exist FROM individuals)                   AS paid_individuals_exist
