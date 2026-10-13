# A0 QuoteResult / offline calculation interface candidate

**This is an A-owned candidate**, not the frozen `contracts/models.py` schema, not a successful `frontend/src/integrations.ts` integration, and not an accepted C `LossResult`. B/D need explicit review and a separate adapter acceptance before displaying outputs as accepted results.

## Data flow

1. Independent C verifier compares frozen Gold to B posted ledger, calculates economic loss by obligation, traceable recoveries, and final observation-time net loss. A0 **does not** infer loss from gross B refunds.
2. A checks coverage under the versioned research contract. Call `calculate_claim(event, contract)` with `event_id`, integer `net_loss_cents` (or `null`), `loss_status` (`verified|needs_review`), and `coverage_status` (`covered|excluded|needs_review`). Only checked coverage and known economic loss produce a determinate payout.
3. Record each *actual run's* assessed payout, plus stable `case_id`, `parent_case_id`, `run_id`, `config_id`, `split`, pre-event `stratum`, `execution_source` and independent provenance/manifest reference. The A0 estimator requires these fields; `case_id` repeats are averaged before computing any group mean.
4. Pass run rows to `calculate_quote(records, config_id=..., contract_version=..., data_version=..., run_manifest_ref=..., target_weights=..., target_volume=...)`. Recompute a **new scenario result** with a changed contract after independently calculating changed event payouts. Never overwrite B/C history.

## B0/B1 estimands

For estimation cases i and repeated runs r: `m_i = mean_r(I_ir)`. B0 = unstratified `mean_i(m_i)`. B1 = `sum_g(w_g * mean_{i in g}(m_i))` with 4 predetermined groups. Scenario cost in *decimal cents* = `target_volume * B0` or `target_volume * B1`. These are **pure indemnity cost illustrations**; they exclude taxes, expenses, capital cost, profit and liability uncertainty. Decimal strings represent fractional averages (not whole-cent posted transactions). No payable amount is fractional: `calculate_claim` gives integer cents with `ROUND_HALF_UP`.

Holdout reference `T(w) = sum_g(w_g * mean_holdout,g(m_i))`, and compare two absolute deviations; the holdout is a dataset reference, **not** true overall market premium. No selection on the holdout results. Same or near-variant `parent_case_id` cannot leak across splits or be double-counted as independent. Data sources (`scripted_test`,`mock_agent`,`engineering_injection`,`observed_agent_execution`) cannot mix in the same quote call.

## Known limitation of A0 candidate

- `reviewed_evidence` is metadata supplied externally; **it is not verified cryptographically by this function**. All outputs remain `illustrative` or uncertain; `commercial_quote` is always false.
- Missing target category or wholly zero observed payout causes `insufficient_evidence`; no scenario cost is supplied, though sample descriptive means can still display zero. Unverified run makes a case's whole estimate unknown; `partial`/`insufficient_evidence` must not be treated as zero.
- `B2` is explicitly `not_fitted`.
- No recurrence/renewal period, cross-event dependence, loss development beyond H, or aggregate limits. No trusted real empirical rate has yet been fitted.
- Changes to model, agent prompt, privilege, controls, business rules or task definitions require new tests. Contract changes alone may be recalculated on the same frozen verified loss ledger, producing a new result version.
- No automated scope adjudication or business responsibility decision: `out_of_scope`/`invalid_input` are reserved contract statuses. Invalid arguments in this A0 pure function raise `ContractError` rather than a pretend QuoteResult.
- **Holdout must be fully reviewed** before citing comparison errors as formal evidence. A0 outputs holdout diagnostics as demonstration only.

## Input and output formats

- Source input: `docs/business/engineering_estimate_input_v0.1.json` (entirely synthetic/scripted).
- Example candidate wire output: `contracts/quote_result_A_v0.1_engineering_example.json`.
- JSON schema: `contracts/quote_result_A_v0.1_candidate.schema.json`.
- Boundary example: `contracts/quote_result_A_v0.1_insufficient_example.json`.
- Meaningful record references must eventually be joined to an actual C LossResult (`case/session/episode/config/run_id` plus evidence checksum). The existing example A0 runs have **no real C LossResult**. Until C and BD approve the input and data binding, D should retain `pending`/`unsupported_contract`.
