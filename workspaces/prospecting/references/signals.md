---
tiers:
  tier1:
  - id: ai_exec_appointment
    freshness_days: 90
  - id: public_ai_initiative
    freshness_days: 60
  - id: ai_rfp_or_procurement
    freshness_days: 45
  - id: earnings_ai_commitment
    freshness_days: 90
  - id: incumbent_standardization
    freshness_days: 120
  - id: ai_governance_formalization
    freshness_days: 90
  tier2:
  - id: ai_hiring_cluster
    freshness_days: 30
  - id: exec_ai_statements
    freshness_days: 60
  - id: ai_vendor_partnership
    freshness_days: 90
  - id: ai_earmarked_funding
    freshness_days: 120
  - id: paid_individuals_present
    freshness_days: 1
    source: warehouse
  tier3:
  - id: generic_ai_marketing
  - id: single_job_post
  - id: industry_trend_mention
  - id: discovery_only
---

# Prospect Signals

**Find evidence that a company is planning, funding, hiring for, testing, deploying, or expanding AI.** Search broadly, identify the actual initiative, and connect it to a relevant person
and potential Example Product use case.

A signal establishes a reason to investigate. It does not establish pain, available budget, purchase intent, or permission to contact an account.

## Signals to look for

Search both company sources and relevant public reporting. AI references in careers pages, press releases, and earnings materials are worth inspecting even when the headline does not
announce an AI program. The last column names the identifier a finding may carry into automated qualification once it is also an active initiative for employee use. Everything else is
`discovery_only`.

### **Dedicated AI hiring**

- Where to look. Company careers pages and job boards
- Evidence to capture. Roles responsible for AI adoption, enablement, transformation, internal agents, or tool evaluation. One substantive posting can identify an initiative; multiple
  openings add context.
- Qualifies as. `ai_hiring_cluster` when two or more AI-adjacent roles (AI enablement, prompt engineering, AI program manager, ML platform) are open at the same time. One role is
  `single_job_post`.

### **AI responsibilities in ordinary roles**

- Where to look. Sales, marketing, finance, operations, and HR job descriptions
- Evidence to capture. Responsibility for introducing AI into the team's work, automating a process, or training colleagues. Familiarity with an AI tool alone is a weaker clue.
- Qualifies as. Discovery only.

### **New AI leadership or team**

- Where to look. Appointment announcements, leadership pages, LinkedIn
- Evidence to capture. An AI leader, transformation office, center of excellence, or implementation team with a stated mandate.
- Qualifies as. `ai_exec_appointment` when the company or credible press announces a named executive appointment with AI in the mandate (Chief AI Officer, VP/Head of AI, Head of GenAI
  programs).

### **Announced AI initiatives**

- Where to look. Press releases, company blogs, strategy updates
- Evidence to capture. Programs, pilots, tool evaluations, standardization, or rollouts. Capture any named team, owner, workflow, investment, partner, or timeline; a stated budget is not
  required.
- Qualifies as. `public_ai_initiative` when the company announces a program with at least one concrete element (budget, timeline, named workflow, or named business unit).
  `incumbent_standardization` when it announces or is reported to standardize on an AI tool for employees. Infer no dissatisfaction or gaps.

### **Executive commitments**

- Where to look. Earnings calls, investor presentations, annual reports, interviews
- Evidence to capture. Plans to invest in AI, change workflows, improve productivity, or expand adoption. Retain specific intent even when tools and workflows are not yet disclosed.
- Qualifies as. `earnings_ai_commitment` when an earnings call or investor day commits to deploying AI in a named internal workflow (not product roadmap features).

### **Employee and leader posts**

- Where to look. Public LinkedIn posts, conference talks, podcasts
- Evidence to capture. Firsthand accounts of implementing tools, running pilots, building workflows, or training colleagues. Record the speaker's role and the scope they actually describe.
- Qualifies as. `exec_ai_statements` when a named executive discusses evaluating or adopting AI tooling specifically enough to name a problem or workflow (interview, keynote, podcast,
  LinkedIn). Employee posts are discovery only.

### **Training and adoption programs**

- Where to look. Company posts, events, careers pages
- Evidence to capture. AI academies, training cohorts, champion networks, workshops, hackathons, or adoption targets connected to company work.
- Qualifies as. `public_ai_initiative` when company-announced with a concrete element. Otherwise discovery only.

### **Vendor and consulting engagements**

- Where to look. Customer stories, partner announcements, implementation case studies
- Evidence to capture. A named company evaluating or implementing AI with a vendor or services partner. Identify the project scope and distinguish implementation from resale or distribution.
- Qualifies as. `ai_vendor_partnership` when a partnership or pilot with an AI vendor or systems integrator for internal use cases is announced.

### **Procurement and budget activity**

- Where to look. RFPs, RFIs, procurement portals, public budgets
- Evidence to capture. Funding or evaluation of AI assistants, enterprise search, knowledge tools, agents, or implementation services. Capture requirements, deadlines, and the responsible
  team.
- Qualifies as. `ai_rfp_or_procurement` for a public RFP, RFI, or procurement notice for AI tooling, enterprise search, or research/knowledge tooling. `ai_earmarked_funding` for a funding
  round, budget line, or capital allocation explicitly earmarked for AI capability building.

### **Internal technical investment**

- Where to look. Engineering blogs, technical talks, job descriptions
- Evidence to capture. Internal assistants, enterprise search, knowledge retrieval, AI integrations, or shared model infrastructure connected to actual company work.
- Qualifies as. `public_ai_initiative` when announced with a concrete element. Otherwise discovery only.

### **Governance and organizational readiness**

- Where to look. Company policies, committee announcements, governance hiring
- Evidence to capture. Establishing approved tools, employee-use policies, review processes, or ownership for AI adoption.
- Qualifies as. `ai_governance_formalization` for a published AI usage policy, governance committee, or responsible-AI framework. Governance alone does not establish a purchase.

### **Expansion, results, or implementation problems**

- Where to look. Earnings updates, customer stories, executive posts
- Evidence to capture. Moving beyond a pilot, adding departments, reporting adoption, or discussing specific cost, quality, integration, or adoption challenges. Preserve the company's
  attribution for claimed results.
- Qualifies as. `public_ai_initiative` or `earnings_ai_commitment` by source when their conditions hold. Otherwise discovery only.


## Interpret the evidence

| Classification | Meaning | Example |
|---|---|---|
| **Active initiative** | Concrete evidence of current funding, hiring for delivery, evaluation, implementation, or expansion. State the actual stage. | A role tasked with delivering the company's AI adoption plan; a department testing an assistant. |
| **Early indication** | Specific interest or intent; execution is unclear. | A CFO announces plans to invest in AI productivity without describing an implementation. |
| **General mention** | AI commentary or marketing without an identifiable company action. | “AI is transforming our industry”; a job requiring familiarity with ChatGPT. Label `generic_ai_marketing` or `industry_trend_mention`. |

Judge the substance, not the number of mentions. **One detailed job posting can establish hiring for an initiative.** It does not establish that the initiative is already deployed. A cluster
of vague postings does not fix missing substance.

Search snippets help locate evidence; read the full source before classifying it. Attribute employee observations and vendor claims to their speakers rather than treating them as
company-wide commitments.

## Identify Example Product relevance

Capture customer-facing initiatives as well as internal ones. Label each finding:

- **Employee use:** AI for research, analysis, company knowledge, documents, reporting, or operational workflows. Find the initiative owner or affected team leader.
- **Customer-facing product/API:** AI embedded in the company's product or customer experience. Find the product or technical owner and assess the research/API opportunity separately.
- **Unclear:** AI activity is evident, but its users or purpose need further research.

A company selling AI may also adopt AI internally; establish each separately. An incumbent rollout does not imply dissatisfaction. Ordinary funding, acquisitions, or expansion provide
context unless the evidence explicitly connects them to an AI initiative.

## Check whether the initiative is current

Record the source date and when it was checked. Verify whether the job remains open, the procurement window remains active, or the program is still being implemented or expanded. An older
announcement can remain relevant when current evidence supports it. Mark missing dates or unresolved status as unknown; do not invent recency.

Count one underlying initiative once, even when several outlets or posts cover it. Preserve updates that show a change in its stage or scope.

## Verified Example Product adoption

These require authorized, privacy-checked warehouse results; public mentions cannot substitute for the account-level checks.

### **Paid individual adoption**

- Meaning and use. Paid individuals are present and no organizational subscription is mapped to the account. Use the completed snapshot and freshness rules in `policy.yaml` and this file's
  frontmatter. Carries `paid_individuals_present`. Outreach may state `policy.prospecting.user_scan.statements.individuals_only` per the talk-track Claim boundaries.

### **Organizational adoption**

- Meaning and use. Outreach may state `policy.prospecting.user_scan.statements.org_adopted` the same way. Adds context; it does not independently establish an outreach opportunity.

### **No adoption found**

- Meaning and use. Make no adoption claim. An empty result is not proof of absence; account mapping may be incomplete.


Do not infer a champion's identity, personal payment, unsanctioned use, or company disapproval. Never expose individual adoption identities, user emails, user or seat counts, queries, or usage timing.

## Record and use findings

Keep **account · initiative and stage · owner or team · evidence classification · source URL, supporting quote, and dates · Example Product relevance**. Mark unknowns explicitly and separate
observed facts from proposed use cases. Retain useful discovery evidence even when it does not qualify.

## Qualification for automated stages

A finding qualifies only when all four hold. It is an active initiative. Its relevance is employee use. It meets the Qualifies as condition for its identifier. Its governing date falls
inside that identifier's frontmatter `freshness_days`. Tier 3 identifiers (`generic_ai_marketing`, `single_job_post`, `industry_trend_mention`, `discovery_only`) never qualify and stay in
the report. `paid_individuals_present` comes only from a privacy-checked warehouse result.

A named-account scan needs one qualified signal. A qualified verdict is not approval to write.
