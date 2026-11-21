# Components audit plan

Scope: all 14 Vue components and components/index.js, read completely including templates and scoped CSS. Preserve Vue 3 script setup, Element Plus, two-space single-quote no-semicolon project style.

1. Reproduce clipboard failure, malformed search history, pending debounce, and concurrent upload state in a Node VM harness using installed Vue SFC compiler.
2. Fix only verified failure ordering, input/state ownership, resource disposal, literal suggestion rendering, accepted MIME types and keyboard/control semantics. Keep existing business features and layout.
3. Coordinate session persistence failure contracts with owner of useLocalStorage; preserve rename drafts on failure and distinguish cancellation from actual errors.
4. Compile every component and execute focused regression checks; record each retained/changed file, rule/evidence range and every new identifier.

Evidence read: CMP-002, ASY-001, ASY-002, ERR-001, ERR-002, HTML-002/008/009/010, NAM-001 fixed GitHub excerpts via verify_evidence.py --show. No new packages.
