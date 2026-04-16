**BIORCE**  
**TRACK 1 — DOCUMENT MANAGEMENT PLATFORM**

# **The Library of Babel — AI Edition**

Sponsor Challenge Brief | Hackathon 2026

*Can AI agents bring order to the chaos of clinical documentation —* **finding, classifying, linking, and surfacing the right document at the right moment?**

## **Why This Matters to Us Right Now**

Clinical trials generate an overwhelming volume of documents — protocols, amendments, informed consents, regulatory submissions, case report forms, safety reports, investigator brochures — scattered across teams, systems, geographies, and filing conventions. At Biorce, we believe that a smart, centralised document backbone is foundational to running faster and more compliant trials.

We have given you a corpus of documents from three fictional Biorce clinical studies. Your job is to make sense of them — automatically, intelligently, and reliably.

## **The Document Corpus**

![][image1]

| Document Class | What It Is | \# in corpus |
| :---- | :---- | :---- |
| **CSP** | Clinical Study Protocol — the "bible" of the trial | 11 |
| **IB** | Investigator Brochure — everything known about the drug | 9 |
| **ICF** | Informed Consent Form — patient consent record | 12 |
| **CRF** | Case Report Form — individual patient visit data | 14 |
| **CSR** | Clinical Study Report — full trial narrative for regulators | 8 |
| **eTMF** | Electronic Trial Master File — regulated document repository | 13 |
| **SmPC / DSUR / DSMB Charter** | Regulatory and governance documents — edge cases | 3 |
| **Synopsis** | CSP base document — Summary of a clinical trial protocol information | 3 |
| **Patient Questionnaire** | Collect Information from patients about health status, symptoms, experiences with care | 1 |
| **Info Sheet** | Informational document about what to expect in a trial | 1 |
| **Medical Publications** | Documents regarding research done in some of the areas pertaining to certain documents | 6 |
| **NOISE** | Unrelated documents that should NOT be classified as trial documents | 10 |

⚠️ The class distribution is intentionally imbalanced to reflect real-world TMF composition. CRFs are the most common document type in any real trial.

## **Deliberate Challenges Built Into the Corpus**

This is not a clean, well-labelled academic dataset. It was designed to reflect the real complexity of clinical document management. Here is what you are up against:

### **1 — Format Chaos**

**MEDIUM**

**7 different file formats in one flat directory**

Documents arrive as markdown, HTML, plain text, email threads, OCR-scanned faxes, and CSV tables. The same document type may appear in three different formats. A CSP might be a clean HTML page or a garbled fax scan. Your classifier cannot rely on format as a signal.

### **2 — Missing and Stripped Headers**

**HARD**

**Several documents have no title, no sponsor name, no study number**

Some documents begin mid-section with no cover page. Others have had their headers stripped entirely. You cannot scan the first five lines for "BIORCE" or a document type keyword — you must classify from body semantics alone.

### **3 — Misleading Filenames**

**DEVIOUS**

**Three files have realistic messy names that lie about their content**

`FINAL FINAL use this consent v2 SIGNED.md` is a superseded ICF. `Scan_0031_compressed.txt` is a protocol synopsis. `Q1_2024_updated_REVIEWED_v3_JL_edits.txt` is a protocol deviation log. The filename is not your friend.

### **4 — Clinically-Relevant Noise**

**HARD**

**Noise files that use clinical trial vocabulary**

A Medical Affairs slide deck quotes Phase II efficacy data. A press release describes the trial design. An investigator CV lists publications on EGFR resistance and references this very study. A CRO vendor contract uses ICH E6 and GCP terminology. A journal article about osimertinib resistance mechanisms reads like an Investigator Brochure. None of these belong in a TMF — but a naive classifier will try to file them there.

### **5 — Genuinely Ambiguous Documents**

**HARD**

**Some documents have legitimate arguments for two different classes**

A covering letter transmitting the Investigator Brochure contains IB summary content AND eTMF correspondence attributes. A DSMB Charter contains stopping rules (protocol-like) AND governance procedures (eTMF-like). DSMB meeting minutes contain safety narratives (SAE-like) AND governance records (eTMF-like). A DSUR overlaps with IB, CSR, and eTMF simultaneously. Your system should handle ambiguity gracefully — not crash on it.

### **6 — Version Chains and Near-Duplicates**

**MEDIUM**

**The same study has a Protocol v1.0, Amendment 1, Amendment 2, and a fax copy of the synopsis**

ICF v2.0 (superseded) and ICF v2.1 (active) differ in exactly three fields. Two files are true byte-for-byte duplicates filed under different names — one with a note explaining the duplication, one without. Can your system detect duplicates and near-duplicates, and correctly label superseded versions?

### **7 — Conflicting Internal Signals**

**DEVIOUS**

**Some documents contain internal contradictions**

A CRF where the lab report on page 3 carries a different study number than pages 1–2. An Investigator Brochure whose cover says "Edition 2" but whose running footer says "Edition 1". An Informed Consent Form where the participant's signature date is five weeks before the ICF version date — a logical impossibility. These errors exist in real TMFs. Your system should classify the document correctly despite the noise.

### **8 — OCR Degradation**

**MEDIUM**

**Fax copies and scanned documents with garbled text**

Some documents were transmitted by fax and scanned. Characters are replaced, words are split with extra spaces, sections are obscured by fax artefacts. Handwritten annotations appear in the text. One document includes a lab report in Italian embedded within an English CRF.

### **9 — Multilingual Content**

**MEDIUM**

**Documents in French, German, and partial Italian**

A French Ethics Committee approval letter. German laboratory normal ranges. An Italian lab report embedded in an OCR-scanned CRF. Clinical trial document types do not change because the language does — your classifier should still get them right.

### **10 — Tabular / Structured Data**

**HARD**

**One file is a CSV patient-level adverse event line listing**

No prose. No headers explaining what the document is. Just rows of comma-separated patient data. This is a real document type in clinical trials (a data listing or line listing, filed in the eTMF or submitted with the CSR). A classifier trained only on text documents will fail entirely.

## **One Thing a Winning Solution Must Demonstrate**

**Intelligent document organisation and retrieval** — showing how document type classification, version management, deduplication, and ambiguity handling can be automated or augmented to meaningfully reduce manual overhead and eliminate misclassification risk.

## **Teaser**

A sponsor just submitted an amended protocol. Somewhere in your folder live 74 documents — consents, site instructions, safety reports, regulatory filings, a faxed synopsis with garbled text, a superseded consent form mislabelled as final, and a vendor invoice that somehow uses GCP terminology. You have 48 hours before your audit. Can your platform find every document that relates to the amendment, identify which ones are outdated, flag the ones with internal inconsistencies, and tell you exactly what needs to be updated — without you reading a single file manually?

## **Evaluation Criteria**

| Criterion | Weight | What We're Looking For |
| :---- | :---- | :---- |
| Classification accuracy (across all 9 classes) | 30% | Precision and recall per class; handling of edge cases and new document types |
| Noise rejection | 20% | Ability to correctly exclude non-TMF documents, especially clinically-relevant noise |
| Robustness | 20% | Performance on stripped headers, OCR degradation, multilingual, conflicting signals, CSV |
| Version and duplicate management | 15% | Detection of superseded versions, near-duplicates, true duplicates |
| Ambiguity handling | 15% | Confidence scoring, flagging of uncertain classifications, graceful degradation |

## **What You Are NOT Expected To Do**

* Build a production-grade eTMF system  
* Achieve 100% accuracy — the corpus is designed so that some cases are genuinely hard even for human experts  
* Process documents in real time at scale

A great solution might achieve 85–90% classification accuracy while clearly articulating where and why it struggles — and proposing a path to improvement.

[image1]: <data:image/png;base64,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>