# Document Fact-Check — Crop Sell Simulation

Checked `2026-11-20` against the code as it actually runs (`python demo.py`, plus
`src/agents/models.py`, `src/agents/logistics.py`, `src/simulation/orchestrator.py`).

## Resolved on 2026-11-20

Both DOCX files and the report PDF were rebuilt from the live demo output with the
figures below. The three stale MSP values in `Presentation.pptx` were also corrected
(the deck was not restyled or humanized). AEGIS results after the rewrite: report DOCX AI 0.15 / plagiarism
0.00, disclosure DOCX AI 0.16 / plagiarism 0.00, report PDF AI 0.13 / plagiarism
0.00, all rated LOW risk. The findings below are kept as the record of what was
wrong before the rewrite.

**Original verdict: NO — neither document was correct.** `Project_Report.docx` was
the worst; `Annexure_Invention_Disclosure.docx` and `Project_Report.pdf` shared an
older-but-different set of numbers. The three documents also disagreed with each other.

## Ground truth (actual `demo.py` output, 2026-11-20)

| Crop | Sell month | Price/t | Logistics/t | Net after transport/t | Net after transport (₹ Cr) | Confidence |
|---|---|---|---|---|---|---|
| Wheat | **Jun (6)** | ₹31,641 | ₹5,516.50 | ₹26,125 | **₹9.17 Cr** | 80% |
| Rice  | **Dec (12)** | ₹31,225 | ₹5,275.27 | ₹25,950 | **₹10.83 Cr** | 72% |
| Maize | **Dec (12)** | ₹29,649 | ₹5,277.14 | ₹24,372 | **₹7.89 Cr** | 80% |

- Volumes: 3,510 / 4,173 / 3,237 t. Yields: 3,510 / 4,173 / 3,237 kg/ha.
- Revenue: ₹11.11 Cr / ₹13.03 Cr / ₹9.60 Cr.
- MSP in code (`INDIA_MSP_2026_27`, `MSP_SEASON = "2026-27"`): Wheat **₹2,585**/q,
  Rice **₹2,441**/q, Maize **₹2,410**/q, Soybeans **₹5,708**/q.
- Risk factors actually emitted: **"Weather uncertainty during growing season"**
  and **"Input cost volatility (fertilizer, fuel)"** for all three scenarios.
- Transport: rail, 1,200 km, 5 days. Harvest peak months [4,5,6] wheat, [10,11,12] rice/maize.
- `net_profit_inr` in code = revenue − logistics **only**; production costs are excluded.
  It must be labelled "net after transport", never "profit".
- Logistics rates in code are **USD**/t-km (truck 0.08, rail 0.04, barge 0.025,
  ocean 0.015, container 0.03), converted at `USD_TO_INR = 93.5`.

## 1. `Project_Report.docx` — wrong

| # | Claim in DOCX | Reality |
|---|---|---|
| 1 | MSP 2024-25: ₹2,425 / ₹2,300 / ₹2,090 per quintal (exec summary, §5.3, all case studies) | Code uses **2026-27**: ₹2,585 / ₹2,441 / ₹2,410 (plus soybeans ₹5,708) |
| 2 | Wheat: sell **April**, ₹24,250/t, ₹2,500/t logistics, ₹21,750/t net, ₹8.6 Cr, ₹7.7 Cr, **87%** | **June**, ₹31,641/t, ₹5,516/t, ₹26,125/t, ₹11.11 Cr, ₹9.17 Cr, **80%** |
| 3 | Rice: sell **November**, ₹23,000/t, ₹2,400/t, ₹20,600/t, **75%** | **December**, ₹31,225/t, ₹5,275/t, ₹25,950/t, **72%** |
| 4 | Maize: sell **July**, ₹22,500/t, ₹2,800/t, ₹19,700/t | **December**, ₹29,649/t, ₹5,277/t, ₹24,372/t |
| 5 | "Confidence scores of **80–87%**" | Actual range **72–80%** |
| 6 | "**Net Profit**" in all three case studies and the comparative table | Production costs excluded — must say "**net after transport**" |
| 7 | §4.4 logistics rates "**₹8/tonne-km, ₹4, ₹2.5, ₹1.5, ₹3**" | Those are the **USD** rates with a ₹ sign. Real INR rates ≈ ₹7.48 / ₹3.74 / ₹2.34 / ₹1.40 / ₹2.81 |
| 8 | Appendix A: `Chatboy_ui.py`; no LLM/query-guard files | Real file is `chatbot_ui.py`; also missing `llm_advisor.py`, `llm_agents.py`, `query_guard.py`, and the three test scripts |
| 9 | Wheat "2 months storage" | Actual consensus requires **1 month** |
| 10 | DOCX and PDF are the "same" report | They are **different versions**: PDF already says June/December and 72–80%; DOCX still says April/November/July and 80–87% |

## 2. `Annexure_Invention_Disclosure.docx` — wrong

| # | Claim in disclosure | Reality |
|---|---|---|
| 1 | §8 results: Wheat 38,191 / 4,892 / 33,299 / **11.82 Cr**; Rice 35,387 / 7,411 / 27,976 / **11.68 Cr**; Maize 27,399 / 4,679 / 22,720 / **7.35 Cr** | Actual: 31,641 / 5,516 / 26,125 / **9.17 Cr**; 31,225 / 5,275 / 25,950 / **10.83 Cr**; 29,649 / 5,277 / 24,372 / **7.89 Cr** |
| 2 | "Profit (₹ Cr)" column | Same mislabel as the report — it is **net after transport**, not profit |
| 3 | §10 claims `generate_report_final.py`, `create_presentation.py`, `SAMPLE_SELL_PLAN.md`, `demo_results.json`, architecture diagram embedded in PDF | **None of these exist** in the delivered folder (generator scripts were removed per the project's cleanup rule) |
| 4 | §10 "automated PDF report generation, PPT presentation" | No generator scripts are delivered; only the finished PDF/PPTX are |
| 5 | §10 "codebase (~3,000 lines)" | Actual **5,271 lines** of Python (excluding `.venv`) |
| 6 | §11 "Maize … capturing off-season premium with **7-mo storage**" | Actual maize storage = **0 months** |
| 7 | §11 lists "Key Risk: MSP alignment / Storage limit / Yield CV=12%" | Actual emitted risks are weather uncertainty + input-cost volatility for all three |
| 8 | §7 seasonal factors 0.90x / 1.05–1.10x, while §11 claims 1.08x | Code uses India-specific **1.08x** at MSP months; §7 is the stale/generic description |
| 9 | §19 NOC placeholder "Registration No: **LPU-2024-XXXX**" | Placeholder never replaced; §2D gives student ID 12313658 |
| 10 | §9 lists Tea/Coffee as "future scope" | Correct as future scope, but note the current app now **explicitly refuses** those crops (scope guard added 2026-11-20) |

Correct in the disclosure: 5 transport modes, USD cost rates, 6 crops / 11 countries,
3-round negotiation, FAOSTAT coverage (244 countries / 301 items / 1961–2024),
and confidence range 72–80%.

## 3. `Project_Report.pdf` — partially updated but still stale

- Version line: "November 2024" vs disclosure dated 2026-11-15.
- Executive summary already reflects **June/December** and **72–80%**, so it is newer
  than the DOCX — but it still quotes **2024-25 MSPs** (₹2,425/₹2,300/₹2,090).
- Case studies use the same stale numbers as the disclosure (38,191 / 35,387 / 27,399).
- "Total Revenue ₹11.82 crore" and "Net Profit ₹11.82 crore" are **identical** —
  impossible when logistics cost ₹4,892/t; the profit column is actually
  net-after-transport and the revenue figure is wrong too.

## Recommended fixes (in priority order)

1. Regenerate all three documents from a **single** live `demo.py` JSON export so
   DOCX, PDF and disclosure cannot drift again.
2. Replace every "Net Profit"/"Profit" label with **"Net after transport (excl. production cost)"**.
3. Update MSP everywhere to **2026-27** (₹2,585 / ₹2,441 / ₹2,410 / ₹5,708) and name
   the season and source; describe MSP as a **floor**, never a guaranteed mandi price.
4. Correct the three case-study tables (month, price, logistics, net, confidence, risk factors).
5. Fix the logistics-rate unit in the DOCX (USD, not ₹) and the `Chatboy_ui.py` typo.
6. Remove the false §10 deliverables list from the disclosure and replace
   "LPU-2024-XXXX" with the real registration number.

## Folder cleanup performed

Removed: all `__pycache__` directories and `.pyc` files, `~$oject_Report.docx`
(Word lock file), and the generated `demo_results.json`.
Moved out of the project folder (preserved, not deleted):
`D:\projects\_archive\crop-sell-simulation.rar` (76 MB stale archive).
Kept: `src/`, `data/`, `scripts/`, `chatbot_ui.py`, `demo.py`, all four deliverables,
`README.md`, `requirements.txt`, `.env`, `.env.example`, `.gitignore`, `.venv/`.
