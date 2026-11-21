# Views second-pass normalization plan

Apply the user-requested writing normalization to every one of the five views while preserving the completed behavioral repairs and rendered layout.

- Keep the existing Vue 3 SFC order, scoped CSS, two-space JavaScript, single quotes and no semicolons.
- Make branch bodies explicit with braces (JS-003); replace collection-length truthiness with exact quantity conditions (JS-002) and use explicit String conversion where applicable (JS-007).
- Remove genuinely unused imports/parameters after checking template and script references (VAR-005). Keep mature function forms and reactive ownership; do not introduce layers or dependencies.
- Normalize multi-attribute Vue elements to one attribute per line (VUE-004) and maintain two-space HTML/CSS formatting (FMT-003). Preserve every attribute value, CSS selector/declaration and visual dimension.
- Re-run the existing 19 behavior/compile/SSR regressions. No mirror tests for formatting-only edits. Record per-file source/evidence mappings and migrate existing report ranges using the captured pre-pass source snapshot.
