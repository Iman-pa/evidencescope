# EvidenceScope Validation Report

**Date:** 2026-07-12
**Drugs:** Kerendia (finerenone), Imaavy (nipocalimab), Ebglyss (lebrikizumab)
**Holdout documents:** CDA-AMC Final Reimbursement Recommendations (SR0893, SR0905, SR0914)
**Input documents:** Combined review PDFs from `data/input/`
**Methodology:** Compare EvidenceScope extracted evidence and suggested scores against the committee's
published rationale for each criterion. Scores are 1–9 (1=strongly unfavourable, 5=neutral, 9=strongly favourable for adoption).

---

## Summary table

| Drug | Committee verdict | Our clinical_benefit | Our safety | Our cost_effectiveness | Our budget_impact | Our equity_access | Our feasibility | Direction match? |
|------|------------------|---------------------|------------|----------------------|------------------|-------------------|----------------|-----------------|
| Kerendia | Reimburse with conditions | 6 | 5 | 4 | 3 | 4 | 6 | Yes |
| Imaavy | Do not reimburse | 4 | 6 | 2 | 2 | 4 | 4 | Yes |
| Ebglyss | Reimburse with conditions | 4 | 6 | 2 | 2 | 4 | 6 | Partial — see below |

---

## Drug 1: Kerendia (finerenone) — Heart Failure

**Committee verdict:** Reimburse with conditions (14-0 vote, Dec 18 2025)
**Our weighted-sum direction:** Moderately favourable (6/5/4/3/4/6 across criteria)

### clinical_benefit — Our score: 6/9 | Committee: moderate-to-high clinical value

Our extraction: "FINEARTS-HF trial (n=6,001) demonstrated finerenone likely results in a clinically meaningful reduction in CV death and worsening HF events compared to placebo plus SOC."

Committee rationale: RR 0.84 (95% CI 0.74–0.95) for composite CV death + total HF events. High certainty for total HF events; moderate certainty for CV death. CDEC voted 14-0 for acceptable clinical value.

**Assessment:** Well aligned. We correctly identified the FINEARTS-HF trial, the composite endpoint direction, and the moderate-to-high certainty grading. Citation was Page 4, which is accurate. Score of 6 (moderately favourable) is appropriate given a statistically significant benefit versus placebo, tempered by a placebo-controlled design with no head-to-head comparators.

### safety — Our score: 5/9 | Committee: manageable, hyperkalemia notable

Our extraction: "Finerenone results in an increase in events of hyperkalemia and worsening of renal function compared to placebo; however, these events were mostly mild-to-moderate and manageable with dose adjustment."

Committee rationale: Hyperkalemia 9.7% (finerenone) vs 4.2% (placebo), but mostly mild/moderate, none fatal. Renal composite higher at 3 months then stable. Overall TEAEs similar between groups.

**Assessment:** Aligned. Score of 5 (neutral) is appropriate — the harms are real but manageable and don't warrant a strongly negative score. The committee's condition requiring prescribing by HF-experienced clinicians is consistent with our 5 (not a deal-breaker, but not without concern).

### cost_effectiveness — Our score: 4/9 | Committee: requires price reduction

Our extraction: "ICER of $77,195/QALY exceeds many payer thresholds without price reduction."

Committee rationale: ICER $77,195/QALY confirmed. Band 2a reduction needed for $50K threshold; no reduction needed at $100K threshold.

**Assessment:** Aligned. Our 4/9 (slightly unfavourable) matches the committee's view that the ICER is above typical thresholds but not prohibitively so — a price reduction addresses it. The committee explicitly made price reduction a reimbursement condition (Table 1, condition 5).

### budget_impact — Our score: 3/9 | Committee: economic feasibility must be addressed

Our extraction: "$107 million over 3 years." Citation: Page 6. ✓ (Fixed from earlier barcode-citation bug — this was the specific criterion where the citation fix was validated.)

Committee rationale: 48,868 patients expected by year 3. $107M incremental over 3 years. Budget impact >$40M in year 3 triggers feasibility condition.

**Assessment:** Aligned. Our 3/9 (somewhat unfavourable) correctly signals this as a concern without being extreme. The committee also did not let this block reimbursement — they addressed it via condition 6. Score of 3 vs. a 5 that might suggest "no concern" would have been wrong; 3 is the right call.

### equity_access — Our score: 4/9 | Committee: acknowledged inequity, no finerenone-specific benefit

Our extraction: "Existing access disparities could limit equitable uptake... rural populations."

Committee rationale: "While CDEC recognized that the risk of HF is disproportionately higher among Indigenous communities, racialized groups, and those of low socioeconomic status, the committee could not find any evidence that finerenone could specifically address this health inequity."

**Assessment:** Aligned. Our 4/9 reflects that equity is a concern not fully addressed by the drug. The committee's exact conclusion is that finerenone doesn't specifically help — our score correctly sits just below neutral.

**One gap:** Our evidence cited Page 41 in the fixture (a specific page about geographic barriers). The committee's framing was broader — it was less about barriers and more about whether finerenone targets underserved groups. This is a subtle distinction the tool can't easily separate, but the score direction is correct.

### feasibility — Our score: 6/9 | Committee: GP-manageable after specialist initiation

Our extraction: "GP monitoring is sufficient after specialist initiation."

Committee rationale: Same — cardiologist for initial diagnosis, GP follow-up. Routine monitoring for hyperkalemia/renal function is standard in HF care.

**Assessment:** Aligned. 6/9 is appropriate.

---

### Kerendia overall

Our scores produce a directionally correct picture: clinical benefit and feasibility are moderately favourable (6); safety and equity are mildly below neutral (5, 4); cost-effectiveness and budget impact are slightly concerning (4, 3). A human reviewer would likely see a case for conditional reimbursement — which is exactly what CDEC decided.

**What we missed:** We didn't identify the indirect comparison vs. SGLT-2 inhibitors (network meta-analysis) as a distinct piece of evidence in our extraction. The committee discussed this in detail (insufficient to draw conclusions, but not disqualifying). This absence from our output isn't wrong, but it's an evidence gap a reviewer would want to flag.

---

## Drug 2: Imaavy (nipocalimab) — Generalized Myasthenia Gravis

**Committee verdict:** Do not reimburse (12-2 vote, initial Jan 28 2026; confirmed after sponsor reconsideration May 27 2026)
**Our weighted-sum direction:** Mixed (4/6/2/2/4/4 — high safety score, low economics, moderate benefit)

### clinical_benefit — Our score: 4/9 | Committee: uncertain, could not confirm comparable value

Our extraction: "Marginal improvement over placebo in MG-ADL (–1.45 pts) and QMG (–2.81 pts), both below MID thresholds. No direct comparative evidence vs. active comparators. ITC results uncertain."

Committee rationale: Identical conclusion. Between-group differences were statistically significant but below MIDs of 2 (MG-ADL) and 3 (QMG) points. NMA insufficient. Clinical importance uncertain.

**Assessment:** Well aligned. Our 4/9 correctly signals below-neutral clinical benefit without being at the floor. The committee's language — "uncertain whether Imaavy demonstrates acceptable clinical value" — maps to a score in the 3–5 range.

**Conflict noted:** Our extraction flagged a conflict between three chunks: scores of 4, 5, and 4 from different document sections. This is actually correct behaviour — the early key messages section was more summary-positive, while the detailed clinical review was more hedged. The merge kept score 4 (highest confidence on the hedged side), which is the right outcome.

### safety — Our score: 6/9 | Committee: no notable signals, comparable to placebo

Our extraction: "TEAEs similar in nipocalimab (81.6%) and placebo (82.7%). SAEs numerically lower with nipocalimab. No opportunistic infections."

Committee rationale: "No notable safety signals." FcRn class profile consistent with other agents. Adverse events comparable to placebo.

**Assessment:** Aligned. Score of 6 (modestly favourable) is appropriate — this is one of the few things in the committee's report that was not a concern about Imaavy.

**Important caveat we captured correctly:** Our extraction noted the OLE data show higher cumulative SAE rates (23.9–28.4%), which the committee acknowledged. This nuance is in our evidence text.

### cost_effectiveness — Our score: 2/9 | Committee: dominated, not deliberated (non-reimburse)

Our extraction: "Nipocalimab dominated by zilucoplan — more costly ($86,026 incremental) and fewer QALYs (–0.04). Annual cost ~$395,085 year 1."

Committee rationale: Since CDEC recommended do not reimburse, they did not formally deliberate on economic conditions. However, from the full review (which we processed), nipocalimab was dominated.

**Assessment:** Aligned. Our 2/9 is appropriate. The annual cost of $395,085 per patient plus dominated economic position is strongly unfavourable.

**Note on conflicts:** Our extraction correctly captured two versions of this — one citing the domination at a high level (score 2) and one citing the full dominated base-case numbers including a 90% price reduction scenario (score 1). The merge kept score 2, which is reasonable: the evidence supports 1–2 range and either would have been defensible.

### budget_impact — Our score: 2/9 | Committee: $154M–$705M over 3 years (not deliberated)

Our extraction: "$705 million over 3 years (Health Canada population) or $154 million (reimbursement request population), both exceeding the $40M threshold annually."

Committee rationale: Not formally deliberated (non-reimburse decision), but budget impact data was available in the full review we processed.

**Assessment:** Aligned. Our 2/9 is correct — this is one of the most unfavourable budget impacts across all three drugs.

### equity_access — Our score: 4/9 | Committee: nonclinical inequity acknowledged, not addressed by Imaavy

Our extraction: "gMG disproportionately affects Black and African American populations, underrepresented in trials. IV infusion access limited in rural regions."

Committee rationale: CDEC acknowledged "significant unmet nonclinical need and health inequity" but concluded nipocalimab does not address it since it requires IV infusion just like existing treatments.

**Assessment:** Largely aligned. Our 4/9 is appropriate. The committee's conclusion was that nipocalimab cannot address geographic inequity because it's also an infusion drug. Our score of 4 (slightly below neutral) is fair, though arguably the committee's framing was more explicitly negative on this point — we might have scored 3.

**What we missed:** The adolescent sub-population equity issue (nipocalimab is the only on-label treatment for adolescents — the sponsor raised this in reconsideration). This is a legitimate equity argument our extraction didn't surface, and CDEC acknowledged it but still found it insufficient given evidence uncertainty. The committee's nuanced position on adolescent equity was not captured in our evidence field.

### feasibility — Our score: 4/9 | Committee: IV infusion, specialist-dependent

Our extraction: "IV infusion (30 mg/kg loading, 15 mg/kg every 2 weeks) requires hospital/specialty infusion infrastructure. Community/rural delivery challenging."

Committee rationale: Geographic barriers to infusion services specifically called out. Similar access issues as existing therapies.

**Assessment:** Aligned. Score of 4 is appropriate for an IV drug requiring specialist infrastructure.

---

### Imaavy overall

Our scores (4/6/2/2/4/4) produce a picture that is directionally aligned with "do not reimburse": clinical benefit uncertain, economics strongly unfavourable, budget impact very high. The one outlier is safety (6/9), which is correct — safety was not a reason for the non-reimbursement decision.

A weighted sum with equal weights would give Imaavy an initial score below 5 (neutral), which correctly signals a more unfavourable profile than Kerendia.

**Critical thing we missed:** The comparator framing is central to this decision. CDEC's core conclusion was that nipocalimab failed to demonstrate "at least comparable value" to existing active therapies (efgartigimod, ravulizumab, zilucoplan, rozanolixizumab). Our extraction captured "no direct comparative evidence" but didn't surface the specific active comparators by name in the evidence summary. A reviewer relying solely on our output would need to know the gMG therapy landscape to understand why a score-vs-placebo showing moderate improvement still triggered a "do not reimburse."

---

## Drug 3: Ebglyss (lebrikizumab) — Atopic Dermatitis

**Committee verdict:** Reimburse with conditions (10-2 vote, Apr 22 2026 — resubmission overturning Oct 2024 non-reimburse)
**Our weighted-sum direction:** Mixed-unfavourable (4/6/2/2/4/6)

### clinical_benefit — Our score: 4/9 | Committee: acceptable, comparable to comparators

Our extraction: "Pivotal RCTs showed significant EASI, IGA, pruritus NRS improvements vs. placebo. Updated NMA and MAICs inconclusive for comparators — upadacitinib 30 mg may be favoured."

Committee rationale: CDEC concluded that, despite methodological limitations in indirect comparisons, "results did not demonstrate significant differences in efficacy outcomes between the treatments" and it was "reasonable to consider them comparable in efficacy." This is the key change from the prior non-reimburse recommendation.

**Assessment: Partially misaligned — this is the most important gap in our output.**

Our score of 4/9 implies slight unfavourability. The committee's conclusion was comparability (which maps roughly to 5/9 — neutral) and explicitly rejected the framing that uncertainty equals inferiority. CDEC's position: "comparable in efficacy" is sufficient for reimbursement when price conditions are met.

This gap is structurally difficult for our tool to resolve. Our 1–9 scale doesn't have a category for "uncertain but not worse than standard of care." Score 5 (neutral/unclear) would be more accurate for this criterion, and the rationale should have foregrounded the comparability finding more explicitly. Our extraction flagged a conflict between four chunks (scores 4, 6, 4, 3), which is correct — different sections of the document give different impressions. The merge settled on 4, which is defensible but undersells the committee's ultimate "comparable" conclusion.

### safety — Our score: 6/9 | Committee: generally favourable, conjunctivitis notable

Our extraction: "TEAEs similar to placebo. Conjunctivitis 4.8–11.0% vs 0–3.5% (placebo). Low SAE rates. NMA favoured lebrikizumab over comparators for overall AEs at week 52."

Committee rationale: Safety described as "generally manageable." Conjunctivitis highlighted as notable adverse event of special interest. NMA results at week 52 favoured lebrikizumab over upadacitinib 30 mg and abrocitinib (both doses). Less frequent maintenance dosing (every 4 weeks vs. dupilumab every 2 weeks) noted as patient-relevant.

**Assessment:** Well aligned. Score of 6 is appropriate. The committee's safety framing was modestly positive — better than or comparable to JAK inhibitors on AEs, which are known for cardiovascular and infection risks.

**What we captured well:** Conjunctivitis as the key adverse event, which the committee specifically flagged. This is a real differentiator and our evidence text names it explicitly.

### cost_effectiveness — Our score: 2/9 | Committee: cost condition imposed; dominated at submitted price

Our extraction: "Lebrikizumab plus TCS dominated by abrocitinib 100 mg. Sponsor's analysis generated fewer QALYs than most comparators at higher cost. CDA-AMC: total cost should not exceed least-costly alternative."

Committee rationale: The economic condition states cost must not exceed least-costly advanced systemic therapy. At submitted price ($37,048 year 1), lebrikizumab is more expensive than abrocitinib 100 mg and upadacitinib 15 mg, less expensive than upadacitinib 30 mg and dupilumab.

**Assessment:** Correct as-extracted (reflecting submitted price), but context is important. Our score of 2 is what the evidence supports at the submitted price. The committee anticipated that the price condition (Table 1, condition 3) would resolve this — i.e., cost-effectiveness becomes acceptable once price is reduced to the level of the least-costly alternative. Our extraction cannot model future price reductions, so 2/9 at submitted price is the honest reading.

### budget_impact — Our score: 2/9 | Committee: feasibility condition imposed

Our extraction: "$127M incremental over 3 years. Total Ebglyss expenditure $472M. Exceeds $40M threshold in year 1 and year 3."

Committee rationale: Identical numbers confirmed. Condition 4 (Table 1) requires budget impact feasibility to be addressed.

**Assessment:** Aligned. Our 2/9 is appropriate. The committee's response was to add a condition rather than deny reimbursement, consistent with treating large budget impact as a hurdle that can be negotiated.

### equity_access — Our score: 4/9 | Committee: mixed — additional option, but access barriers remain

Our extraction: "Predominantly White trial populations. Rural/remote access to specialists limited. Patients without private insurance face barriers. Less frequent dosing may help."

Committee rationale: CDEC noted lebrikizumab "may serve as an additional advanced therapy option for patients eligible for public drug program coverage." Also noted less frequent maintenance dosing (every 4 weeks) vs. dupilumab (every 2 weeks) as a patient-relevant advantage. Geographic barriers acknowledged.

**Assessment:** Slightly below what the committee emphasized. The committee's framing of lebrikizumab as an additional option expanding access within the public system is more positive than our score of 4/9 conveys. Score of 5 would have been closer to the committee's net position. The dosing-schedule equity angle (less frequent injections for patients who find biweekly difficult) was identified in our evidence but weighted less than the barriers in our score.

### feasibility — Our score: 6/9 | Committee: subcutaneous, feasible, less monitoring than immunosuppressants

Our extraction: "Subcutaneous self-injection. Can be prescribed by dermatologists, allergists, or GP with sufficient expertise. Less monitoring than conventional immunosuppressants."

Committee rationale: Same. Noted less frequent monitoring as advantage. Specialist prescribing requirement acknowledged as potential barrier in some regions.

**Assessment:** Aligned. Score of 6 is appropriate.

---

### Ebglyss overall

Our scores (4/6/2/2/4/6) paint a picture that understates the case for reimbursement compared to what CDEC concluded. The committee's logic:
1. Comparable (not inferior) clinical value vs. active comparators ✓ (we scored this as slight unfavourability, which is the main gap)
2. Unmet need in patients who can't use JAK inhibitors or fail biologics ✓ (we captured this partially)
3. Price condition resolves cost-effectiveness concern ✓ (we correctly flag the concern but can't project post-condition outcomes)
4. Safety profile is favourable relative to JAK inhibitors ✓ (well captured)

The honest assessment is that our tool would likely not produce a scorecard that a naive reviewer would interpret as "reimburse with conditions." The clinical benefit score (4) and economic scores (2, 2) dominate the weighted sum in a negative direction. A reviewer would need to understand that 4/9 on clinical benefit can still support reimbursement if the comparator bar is "not worse than" rather than "better than."

---

## Cross-cutting observations

### What the tool got right

1. **Evidence fidelity:** For all three drugs, the extracted evidence statements match the numbers and conclusions in the holdout documents. ICERs, trial names, effect sizes, and trial populations were all correctly identified. This is the core function and it works.

2. **Citation accuracy (post-fix):** Kerendia budget_impact correctly cites Page 6 — this was the specific case where the barcode-footer citation bug would have caused a wrong citation (the barcode "111000" would have been cited instead of "[Page 6]"). The fix worked.

3. **Conflict detection:** All three drugs triggered `has_conflicts: True` because different document chunks presented the same evidence with different emphases. The conflict logging correctly identified these and the merge logic preserved the best extraction. This is a real feature, not a defect.

4. **Safety scores are reliable:** For all three drugs, safety was scored 5 or 6 — correctly identifying that none of these drugs has a disqualifying safety profile. None of the three committee decisions turned on safety.

5. **Direction for clear non-reimburse:** For Imaavy, the tool correctly produced a low-clinical-benefit + very-low-economics profile. The combination of 4 clinical benefit + 2 cost-effectiveness + 2 budget impact unambiguously signals a drug that faces a high bar for reimbursement.

### Systematic gaps

1. **"Comparable value" is not well-represented on a 1–9 scale.** The committee's CDEC framework distinguishes between "superior value," "comparable value," and "inferior value." Our 1–9 scale maps poorly to this: score 5 means neutral/unclear, not "comparable." For Ebglyss, where the key finding was that indirect comparisons "did not show significant differences," a score of 4–5 is technically correct but misleads a human reviewer who might expect a reimburse candidate to score 6 or 7 on clinical benefit. This is a design issue to discuss, not a bug.

2. **The tool cannot distinguish primary vs. supplementary evidence.** For Ebglyss, the pivotal RCTs (3 trials, high certainty vs. placebo) exist alongside methodologically limited indirect comparisons. Our scoring blended these — the conflict system captures the tension but doesn't communicate hierarchy. The committee's eventual "reimburse" was driven primarily by the ITC conclusions, which required expert judgment about whether imprecision = inferiority.

3. **Adolescent subpopulations not surfaced for Imaavy.** The VIVACITY-MG adolescent trial (N=8, VIBRANCE-MG) was noted in the committee's equity and unmet-need deliberation as a specific reason why the non-reimburse decision was painful. Our extraction described this as "low certainty evidence" and didn't flag the adolescent-specific equity issue. A reviewer relying on our output alone might not understand why the committee agonized over this decision.

4. **Price conditions cannot be reflected in extracted scores.** For both Kerendia and Ebglyss, the committee imposed price reductions as reimbursement conditions. Our cost-effectiveness scores reflect the submitted price and correctly flag the concern, but there's no mechanism to say "this concern would be resolved by a 25% price reduction." The tool is correctly designed (we score what the evidence shows), but reviewers should be aware that a low cost-effectiveness score can coexist with a "reimburse with conditions" outcome.

5. **Comparator landscape not surfaced.** For Imaavy and Ebglyss, the committee's conclusions were heavily driven by indirect comparisons vs. specific named drugs (efgartigimod, ravulizumab, upadacitinib, abrocitinib, dupilumab). Our clinical_benefit evidence summaries note "no direct comparative evidence" but don't name the specific comparators that matter for the decision. A reviewer without specialist knowledge would not be able to evaluate the significance of this gap from our output alone.

### Recommendation for demo preparation

The tool works well as a rapid evidence extraction engine and a first-pass flagging mechanism. For the July 15 demo, the most important thing to communicate is the design principle: we score what the document says at the submitted price, and human reviewers supply the deliberative judgment about whether a set of scores supports conditional reimbursement. The Kerendia case makes this clear and is the strongest validation. The Ebglyss case is the most honest illustration of the tool's limits.

---

## Extraction run metadata

| Drug | Input file | Pages | Words | Chunks | Tokens in | Tokens out | Cost |
|------|-----------|-------|-------|--------|-----------|------------|------|
| Kerendia | SR0893r-Kerendia_combined.pdf | ~54 | ~20K | (prior run) | — | — | — |
| Imaavy | SR0905_Imaavy_DRAFT_combined.pdf | 54 | 23,856 | 4 | 47,318 | 4,311 | $0.207 |
| Ebglyss | SR0914-Ebglyss_combined.pdf | 57 | 33,561 | 5 | 65,673 | 5,401 | $0.278 |

Kerendia fixture was loaded from a prior run (2026-07-11). Imaavy and Ebglyss run 2026-07-12.
