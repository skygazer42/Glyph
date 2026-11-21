# Round 3: tooling, knowledge, packs, and pipeline review

Scope: the 88 files recorded in the round 2 tooling completion manifest. This lane owns `app/knowledge`, `app/agents/{packs,pipeline,dsl_generator}`, `scripts`, `examples`, database seed scripts, and its three existing regression files. Other agents' files and the historical round 2 evidence remain untouched.

1. Re-read NAM/FUN/DAT/ERR/DES guidance and run the three existing regression modules before edits.
2. Read every owned file for names, function responsibility, main business flow, established data contracts, dependency imports, and `None` ownership. Follow actual callers before changing interfaces.
3. Remove confirmed required-dependency probes, invented callable sentinels, dead availability flags, and unsupported protocol fallbacks. Retain real lazy-resource state, absent query results, disabled features, and external protocol variation with a concrete explanation.
4. Rename misleading internal helpers and simplify branches at their semantic owner. Do not invent business defaults, dependencies, abstractions, compatibility layers, or new Python modules.
5. Add meaningful behavior regression coverage before behavior changes; use existing coverage for mechanical simplification. Run relevant regressions after each coherent change.
6. Finish with the three regression modules, targeted Ruff/mypy/compile checks, and a per-file review record plus independent `tooling-review.md` in this round 3 directory. Report missing external runtime prerequisites honestly without installing or invoking external business services.

Confirmed initial issues: `document_loader.py` treats declared `python-docx` as an optional callable; the intent classifier maps malformed JSON or missing intent to `None`, making downstream fabricated default routing possible. Both require direct contracts, not another wrapper.


## Bounded follow-up after parent review

Source freeze is temporarily lifted only for the confirmed graph/document-loader omissions. Do not broaden the previous file review or add Python modules.

1. Verify graph embedding-model and dimension configuration contracts; remove redundant empty-string/default coercion, and reject a selected nonpositive configured OpenAI dimension instead of substituting 1536.
2. Verify the document loader owns keyword extraction; compute keywords directly, declare `_extract_content` as `str` when all branches return text or raise, and name deduplication state after image URLs.
3. Add regression coverage for custom-model dimension rejection and correct keyword/image output in the existing knowledge/pipeline test module; run the limited regression before and after changes.
4. Re-run the owned test modules and scoped Ruff/mypy/syntax checks, refresh the 88-file frozen hashes/report and state the final freeze explicitly. Previous no-remaining-omission wording is withdrawn; this follow-up addresses only the parent-confirmed locations.


Additional parent-confirmed candidates are limited to `dialog_agent.py` required query strings, `rewrite_agent.py` history fields after checking the SessionStore producer, `image_retrieval.py` guaranteed regex-group strings, and vector reranking of this module's own PolicyDocument.model_dump/search-result dictionaries. Remove only proven redundant coercions and fabricated score defaults; retain the optional-rerank failure strategy. Record real optional LLM credential candidates, platform/rule metadata and streaming deltas rather than replacing them mechanically.
