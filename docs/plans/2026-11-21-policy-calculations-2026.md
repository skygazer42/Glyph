# 2026 Policy Calculations Implementation Plan

**Goal:** Add eight source-backed calculators for policies implemented in 2026, available through the saved-rule list, draft preview, and rule testing APIs.

**Architecture:** Reuse the existing YAML DSL, explicit helper allowlist, input forms, and authentication. Add bounded pure calculations for four national trade-in scenarios and four Jinan housing scenarios. Keep policy source clauses, dates, limitations, and example inputs alongside each rule. A calculation is an estimate from supplied facts, not an administrative eligibility decision.

**Tech Stack:** Python, Pydantic v2, Decimal, PyYAML, existing PolicyEngine and FastAPI; Vue 3 and Element Plus for the existing form.

## Scope and design

- National: 2026 appliance trade-in, digital/smart product purchase, automobile scrapping/replacement, automobile transfer/replacement. Read the complete official MOFCOM rules, including automobile rounding and date/ownership requirements; retain snapshots and extraction manifests.
- Jinan: home renovation provident-fund withdrawal, talent home-purchase subsidy, annual property-fee withdrawal, annual heating-fee withdrawal. Reuse collected official 2026 sources, preserve account-balance/previous-claim/rate suspension constraints, and explicitly limit talent calculations to the post-transition policy.
- Use status CALCULATED for estimates; INELIGIBLE, INVALID_INPUT, MANUAL_REVIEW, and SUSPENDED remain visible when relevant. Every helper returns status, amount (yuan), and reason. Do not default unverified eligibility to true. No live budget, property, talent, or social-insurance database checks are implied.
- No dependency changes, no database migrations, no deletion or rewriting of legacy rules or existing policy sources. New identifiers are unique. Source snapshots distinguish publication date from policy application year.

## Ownership

1. components_review: four national YAML files, `trade_in_calculations.py`, national tests, new national source snapshots/catalog.
2. views_review: four Jinan YAML files, `housing_calculations.py`, housing tests, housing source mapping/catalog.
3. Parent: helper registration, query-aware candidate selection so more than five active rules remain reachable, existing form labels/options/statuses, integration tests, authenticated running-service checks and final catalog.

## Test and verification sequence

1. Capture legacy rule hashes; run existing draft/evaluator tests before edits.
2. Write failing behavior tests in each owned lane before new helper implementations. Verify actual policy examples, caps, exact threshold values, invalid/missing/non-finite inputs, date boundaries, repeated benefits and unsupported categories.
3. Register only explicitly named helpers in the sandbox. Preserve existing arbitrary-code rejection and saved/draft equivalence.
4. Add rule-selection regression tests proving all eight rules can be surfaced in a five-candidate planner context for relevant queries.
5. Give fields Chinese labels and supported option lists from their declared input contracts; keep missing required values unfilled. Ensure CALCULATED is displayed as a calculation, not approval.
6. Run focused pytest, Ruff, syntax/type checks supported by the project, and the frontend lint/build/static contracts for touched frontend code.
7. Verify actual authenticated `/api/dsl/list`, rule detail, `/test`, and `/preview` for all eight new rules. Check source/version metadata and all legacy rule file hashes. If the service needs refreshed Python code, restart only the identified task-local API service, preserving its configuration and existing endpoints.
8. Publish the eight-rule catalog, examples, test evidence and explicit remaining external verification limits.

## Acceptance

Eight distinct current policy calculators are listed by the running API, return the independently calculated expected yuan amounts through both saved and draft execution, reject invalid/out-of-scope cases, and are discoverable by the rule agent. Original rules and previously imported policy data remain intact. Reports give exact test counts and no blanket policy-validity or eligibility-certification claims.
