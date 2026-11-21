# Components full-line review plan

Scope: all 14 Vue SFCs plus the three-export components/index.js. Review the entire current template/script/style contents, including retained lines, against all 137 registered rules; distinguish applicable contracts, optional recommendations and framework/language exclusions.

1. Save exact pre-review bytes and hashes in a lane-owned snapshot before edits.
2. Read all relevant guideline chapters and the fixed-source excerpts selected by every applicable rule, reusing the already read evidence only where its contract is unchanged. Mark React, TypeScript, class and Tailwind-only rules explicitly inapplicable rather than claiming they were enforced.
3. Read each final component in full, including scoped CSS and callers/owned resources. Inspect props/macros/controlled values, input ownership, keys, falsey/default behavior, sorting, identifiers, DOM names/labels, async failure ordering and resource cleanup. Record recommendations retained for actual project reasons separately from defects.
4. Reproduce any newly confirmed behavior defect before the minimum reversible fix; preserve public interfaces and layout. Do not edit another lane or install dependencies.
5. Run existing regression/static checks; record final segment ranges and full/excerpt hashes only after edits. Provide the full rule-by-rule applicability map, exact repaired-code evidence and identifier positions, explicit residual verification limits, and old-to-new line migration for the leader's evidence refresh.

The hash/range inventory records the manual read boundary; it is not offered as proof that static tooling or line counts establish arbitrary semantic compliance.
