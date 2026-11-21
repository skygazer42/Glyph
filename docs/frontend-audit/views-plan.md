# Views audit plan

Scope: review every template, script and style in the five `web/src/views/*.vue` files. Preserve Vue 3, Element Plus, existing JavaScript formatting and visual layout.

1. Read fixed skill evidence and actual API contracts; identify concrete security, asynchronous ownership, lifecycle and failure defects.
2. Before behavior changes, reproduce them using existing Vue compiler and Node VM with controlled API/timer stubs.
3. Make narrowly scoped fixes: escape external text before generating trusted formatting tags; dispose component-owned animation/request/timer resources; prevent stale task writes and false success; preserve submitted drafts on failure.
4. Re-run regression cases and compile all five SFC scripts/templates. Record each file, source mapping and every new identifier. No new dependencies, commits or deployments.

Known verification limits: VM tests isolate script behavior rather than mount Element Plus or contact the real backend. Production build is owned by the main agent.
