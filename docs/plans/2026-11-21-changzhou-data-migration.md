# Changzhou government conversation data migration

**User direction:** The platform serves Changzhou, Jiangsu. Replace the incorrectly selected Jinan/Shandong local data throughout the active system; continue enriching government conversation data with official service guides and traceable Q&A.

## Outcome

- Keep nationally applicable official policies; replace local policy/guide content with Changzhou and applicable Jiangsu material.
- Collect approximately 40 distinct official local sources and 80+ local Q&A across health insurance, social insurance, employment, welfare, birth/childcare, education, identity services, business services, housing and talent. Add source-backed national 2026 Q&A where useful.
- Replace four Jinan calculators with independently sourced Changzhou calculators. Do not transplant old parameters by renaming a city.
- Make all active retrieval paths consistent: local source files, upload/parse/embed status, Milvus, FAQ, LightRAG, SQL/seed content, domain defaults and visible examples.

## Safe execution and ownership

1. Parent inventories active stores and snapshots affected local records/files into a dated archive outside indexed source directories. Preserve unrelated code, conversations, credentials and national data. Do not clear entire databases or collections.
2. components_review collects non-housing Changzhou/Jiangsu official sources and Q&A in its new services paths.
3. views_review collects housing/talent sources and Q&A, implements source-specific Changzhou calculations and tests in its assigned files.
4. Parent migrates active data, replaces the main FAQ only with verifiable sourced entries, updates the region defaults/examples and affected data seed mechanisms, and integrates final calculations.

## Quality contracts

- Every source retains raw bytes, a readable body, official URL, issuer/publisher, dates, geographic scope, retrieval date and body hash. Distinguish policy, official service guide, official Q&A and interpretive material.
- Never invent a material list, statutory timeframe, fee, eligibility condition, contact, counter address or subsidy amount. State district-specific scope explicitly. Avoid expired activities and superseded benefit amounts.
- Every curated answer records the source URL, exact support quote, source body hash, region and collection date. Unknown local details remain unknown; use official channels for confirmation.
- Nationally applicable documents hosted on local government domains remain national documents; classify by actual content and jurisdiction, not hostname alone.
- Archived Jinan/Shandong material cannot remain in an indexed directory, an active rule registry or an answer cache.

## Verification

1. Baseline file hashes and exact store IDs/contents before mutation; archive affected records and files with a restore manifest.
2. Regression tests for FAQ source/region/expiry behavior and calculator replacement before code changes. Keep old rule tests as historical records only where appropriate; active tests target Changzhou.
3. Import all accepted sources/curated Q&A with stable IDs and exact readback. Check no retired IDs remain active and all retained national record contents are unchanged.
4. Rebuild or replace the affected graph namespace from the new official sources; old graph caches cannot answer Jinan questions as local policy.
5. Replace identifiable Jinan demonstration SQL rows with source-backed Changzhou rows, preserving schema and unrelated user-owned records. Seed scripts must not generate fabricated Changzhou benefits by a string substitution.
6. Verify actual authenticated document listing/workspace/search, FAQ and new saved/draft calculators, and inspect domain/UI examples for stale default city content.
7. Run focused tests, Ruff, mypy and relevant frontend build checks. Report actual counts, collection scopes, active stores and any remaining limitations.

**No automatic commit, dependency installation or blanket schema migration.** The user has authorized replacing the wrong regional data; reviewable archives make the replacement reversible.
