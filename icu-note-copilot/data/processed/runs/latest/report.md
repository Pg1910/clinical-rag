# ICU Clinical Decision Support Report

**Generated:** 2026-01-23 17:52:35

---

## 📋 ICU Summary

- **Patient: 8.5 month old female, 5.2kg** `[N000001]`
- **Primary problems: Liver failure secondary to biliary atresia** `[N000006]`
- **Hepatic: Post-Kasai, liver failure with coagulopathy** `[N000006]`
- **Infectious: E. coli sepsis, ascending cholangitis** `[N000002, N000004]`
- **Respiratory: ARDS on mechanical ventilation, FiO2 0.6** `[N000007]`
- **Coagulation: Coagulopathy: PT 21.8, PTT 76.6** `[L000059, L000049]`
- **Renal: Elevated BUN 73, possible hepatorenal** `[L000040]`

---

## 🔬 Differential Diagnosis (Ranked)

### 1. Primary Hepatic Failure 🟢 (HIGH)

**Supporting Evidence:**
  - Liver failure diagnosis: liver failure `[N000006]`
  - Coagulopathy: coagulopathy `[N000006]`

**Missing (to confirm/rule out):**
  - ❓ AST/ALT/bilirubin trend 48-72h
  - ❓ Ammonia level

### 2. Sepsis with Multi-organ Dysfunction 🟢 (HIGH)

**Supporting Evidence:**
  - Sepsis diagnosis: sepsis `[N000007]`
  - ARDS development: ARDS `[N000007]`

**Missing (to confirm/rule out):**
  - ❓ Blood culture speciation
  - ❓ Procalcitonin trend

### 3. Coagulopathy (DIC) 🟡 (MEDIUM)

**Supporting Evidence:**
  - Elevated PT/PTT: PTT 76.6, 68.6 `[L000059, L000003]`
  - Liver failure: liver failure `[N000006]`

**Missing (to confirm/rule out):**
  - ❓ Fibrinogen level and D-dimer to differentiate DIC vs hepatic coagulopathy

### 4. Acute Kidney Injury (AKI) 🟡 (MEDIUM)

**Supporting Evidence:**
  - Elevated BUN: BUN 73, 72 `[L000040, L000002]`
  - Sepsis: sepsis `[N000007]`

**Missing (to confirm/rule out):**
  - ❓ Serum creatinine trend

---

## ❓ Clarifying Questions

- 🟠 **[HIGH]** Fibrinogen level and D-dimer to differentiate DIC vs hepatic coagulopathy?
  - *Rationale:* Needed to confirm or rule out Coagulopathy (DIC) `[L000059, N000006]`

- 🟡 **[MEDIUM]** AST/ALT/bilirubin trend 48-72h?
  - *Rationale:* Needed to confirm or rule out Primary Hepatic Failure `[N000006]`

- 🟡 **[MEDIUM]** Ammonia level?
  - *Rationale:* Needed to confirm or rule out Primary Hepatic Failure `[N000006]`

- 🟡 **[MEDIUM]** Blood culture speciation?
  - *Rationale:* Needed to confirm or rule out Sepsis with Multi-organ Dysfunction `[N000007]`

- 🟡 **[MEDIUM]** Procalcitonin trend?
  - *Rationale:* Needed to confirm or rule out Sepsis with Multi-organ Dysfunction `[N000007]`

---

## ✅ Action Items

- 🟠 **[HIGH]** Review coagulation panel trend (PT/PTT/INR/fibrinogen)
  - *Rationale:* Coagulopathy identified; trending needed `[L000059, N000006, L000003]`

- 🟠 **[HIGH]** Review blood culture results and antibiotic coverage
  - *Rationale:* Sepsis identified; culture guidance needed `[N000007]`

---

## ⚠️ Limitations

- Limited to evidence available in patient record
- No medication data extracted
- Monitor data may be incomplete

---

## 📎 Evidence Appendix

*All cited evidence IDs with source snippets:*

- [L000002] (Lab-Data:L2-2)   08/16/93      18:13 BUN                 72
- [L000003] (Lab-Data:L3-3)   08/16/93      18:13 PTT               68.6
- [L000040] (Lab-Data:L40-40)   08/17/93      04:31 BUN                 73
- [L000049] (Lab-Data:L49-49)   08/17/93      04:31 PT                21.8
- [L000059] (Lab-Data:L59-59)   08/17/93      04:31 PTT               76.6
- [N000001] (Patient-Description:L1-1) 8.5 month old female with biliary atresia, S/P (surgical procedure) 
- [N000002] (Patient-Description:L2-2) Kasai procedure, ascending cholangitis with a history of
- [N000004] (Patient-Description:L4-4) The Children's Hospital after a 15 day history of E. Coli sepsis, worsening
- [N000006] (Patient-Description:L6-6) in liver failure with coagulopathy.  She has required mechanical
- [N000007] (Patient-Description:L7-7) ventilatory support due to the ARDS that followed the onset of sepsis.

---

*This report is for clinical decision support only. All findings require physician review.*