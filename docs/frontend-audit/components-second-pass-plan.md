# Components second-pass plan

User correction requires an implemented guideline rewrite in every maintained component file, including the six files previously retained. Existing nine component corrections remain part of the final delta; do not invent additional behavior or layout changes to meet the file count.

- EmptyState: mark the already redundant visual icon as decorative; retain visible title/description and layout.
- QuickNav: express the existing navigation landmark as native nav, preserving real router-links, paths and classes.
- SkeletonLoader: complete count's runtime prop contract with a nonnegative integer validator; preserve its default and accepted rendering behavior.
- Text2SQLResult: replace abbreviated local value/column names with names that describe numeric chart values and columns; keep calculations and output unchanged.
- ThemeToggle: derive the repeated action label once from the shared theme state and bind it consistently to title and aria-label.
- components/index.js: delete the inaccurate claim that the three-entry barrel exports all components; preserve its exact named re-export API.

Read fixed evidence before edits; retain small changes and no new packages. Reuse component regression and full static validation. Record all fifteen final changed files, exact ranges, naming provenance, and migration of prior retained audit conclusions. Do not add mirrored behavior tests for spelling, formatting or unchanged calculations.
