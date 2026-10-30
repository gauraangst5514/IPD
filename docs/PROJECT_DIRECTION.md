> Historical design/change record. For the current 30 October implementation, model availability and deployment failure, use [COMPONENT_GUIDE.md](COMPONENT_GUIDE.md) and [INTEGRATION_HANDOFF.md](INTEGRATION_HANDOFF.md).

# IntelliClaim: a feasible research direction without insurer records

Decision date: 29 October 2026. This specifies the next research work; learned
damage re-identification and model results are not implemented by this patch.

## Recommendation

Focus on **reused photographic evidence and repeated vehicle-damage detection
for motor-insurance claim investigation**. Keep the damage detector, upload
workflow, evidence persistence, investigator dashboard and audit trail. Make
damage re-identification the learned component; retain simple image hashes as
baselines. A GNN is an optional later experiment if genuine relational labels
become available.

The strongest reason to proceed is the fit between the task, your existing
vision work and a directly relevant released research resource. The strongest
reason not to proceed is that this remains a narrow fraud indicator: image
similarity cannot establish fraudulent intent, policy coverage or entitlement.
Your evaluation must measure evidence retrieval, not claim fraud accuracy.

This is worth doing if the submission demonstrates an evaluated improvement
over perceptual hashing and helps an investigator find relevant prior evidence.
Merely wrapping YOLO, fixed scores and a graph visualization is not a strong
research contribution. This is also an established research task; do not call
the combination itself novel or claim an entirely new fraud-detection method.

## Problem statement

Develop and evaluate a claim-evidence retrieval system that identifies identical
photographs, transformed copies and candidate recurring vehicle damage across
motor-insurance submissions. Compare full-image and damage-region representations
against exact and perceptual hashing baselines. Present matched historical
evidence and uncertainty to an investigator, while distinguishing ordinary
resubmissions, visually similar unrelated damage, and unavailable evidence.

The concrete question: does damage-region representation improve retrieval and
reduce false alerts compared with whole-image matching under realistic benign
transformations and hard negative examples?

## The directly relevant paper and available resources

Maiano et al., *A deep-learning-based antifraud system for car-insurance claims*,
Expert Systems with Applications 231, 120644 (2023).

- Paper: https://doi.org/10.1016/j.eswa.2023.120644
- Author repository: https://github.com/Assicurazioni-Generali/damage-similarity
- Linked resources: https://drive.google.com/drive/folders/1VKMuGIejowfg7xylZsPKJ9VGdaxNWTYv

The paper studies damage re-identification for investigation, combining visual
matching and vehicle information. Its repository describes OSNet embeddings and
cosine similarity, with mAP 78.7% and Rank-1 81.8% reported in the README. These
are author-reported results, not our measurements. The linked folder lists a
paper.zip archive around 2.55 GB and damage-model archives around 1.15 GB. Folder
listing was verified; archive contents, successful downloads, exact license and
reproducibility were not verified. The legacy environment and incomplete setup
instructions need an initial reproduction check before committing the schedule.

### Dataset decisions

| Resource | Role | What it cannot establish |
|---|---|---|
| Author damage-similarity resources above | First choice for real same-damage retrieval benchmark, after inspection | Fraudulent intent or success on your insurer population |
| Official CarDD: https://cardd-ustc.github.io/ | Existing damage detector; source images for labelled transformation experiments, subject to license | Original fraud labels, real claim histories, or same-damage identities unless independently verified |
| Consented multi-view damaged-vehicle photos collected by your team | Small external same-damage evaluation | Representative insurer fraud prevalence |
| Vehicle Claim Fraud Detection: https://www.kaggle.com/datasets/shivamb/vehicle-claim-fraud-detection | Optional separate tabular fraud-classification benchmark | Paired damage photos or a trustworthy garage/claimant relationship graph |
| Underwriting Fraud: https://www.kaggle.com/datasets/brunordeprez/underwriting-fraud-real-worldanonymised | Optional separate graph-method benchmark | Motor-damage fraud validation |
| iFraudSimulator: https://github.com/BavoDC/iFraudSimulator | Controlled network stress tests if graph research remains mandatory | Real-company detection performance |

The commonly used vehicle-claim tabular benchmark has 15,420 records and 923
fraud labels according to the 2025 Journal of Big Data study below. It can support
an additional classifier experiment. Its provenance, column semantics, label
quality and reuse terms require inspection. Do not treat row IDs or a shared car
make as evidence of collusion, and do not randomly attach CarDD images to rows.

Supporting dataset study: https://doi.org/10.1186/s40537-025-01217-3

## What to build next

1. **Access and data audit, first half-day.** Download and inspect the author
   archive using its stated terms. Locate real versus generated examples,
   damage-identity labels, query/gallery definitions and pretrained weights.
   Record a dataset manifest and license. If access or labels fail, immediately
   use a clearly labelled transformed-image benchmark; do not spend days waiting.
2. **Baseline benchmark, next half-day.** Compare SHA-256 exact matching and
   pHash+dHash retrieval. Include resizing, JPEG recompression, crops and altered
   brightness. These labels mean “same source photo,” not “confirmed fraud.”
3. **Learned retrieval, one to two days.** Use a pretrained visual embedding and
   cosine retrieval as a whole-image baseline. Compare embeddings from the
   existing YOLO damage crops. Evaluate the author's OSNet weights if usable;
   do not start by reproducing its entire old software stack. If training is
   feasible, fine-tune with same-damage identities/triplets and held-out identities.
4. **Match decision, half-day.** Learn a same-damage pair classifier or select a
   similarity threshold on validation pairs. Inputs may include embedding
   similarity and image-level signals. Its target is same-damage versus different
   damage, not fraud. Add an inconclusive outcome for weak evidence. Calibrate
   match probabilities only if needed; do not rename them fraud probabilities.
5. **Investigator workflow, one day.** Retrieve the top historical candidates,
   show both images and damage crops, claim IDs, match type and model version.
   Store reviewer disposition separately from training labels. A reviewer can
   mark a normal resubmission without pretending that a rejection equals fraud.
6. **Evaluation and report, one to two days.** Freeze the model and protocol,
   compare baselines and ablations, inspect hard false positives and write the
   limitations. Record a reproducible demonstration and backup video.

If fewer than three days remain, complete the transformation benchmark and
evidence workflow first. Label natural multi-view recognition as future work
unless you actually test it. If your course requires a GNN, keep the graph track
as an explicitly separate public-data/simulation experiment; do not claim its
results validate the live motor-claims app.

## Evaluation that makes the project defensible

- Separate **same-photo retrieval** from **same-physical-damage retrieval**.
  Transformations of one photo test the former; they do not establish the latter.
- Split training/validation/test by original vehicle/damage/source identity
  where available. All transformations and crops from a source stay together.
  Test queries and galleries may share held-out damage identities by design;
  those identities must not appear in training.
- For testing, construct a gallery of earlier observations and submit held-out
  queries. Include queries with no match in the gallery. Do not manufacture
  genuine timestamps for datasets that lack them.
- Include difficult different-damage negatives: same make/color/body panel and
  similar dents/scratches. Also include permitted same-claim reuploads.
- Report Recall@1/5, retrieval mAP, false alerts per 100 nonmatching queries,
  precision/recall of the match decision at a validation-selected operating
  point, latency and gallery size. Report synthetic versus real separately.
- Tune on validation only. Compare hashing, whole-image embeddings, damage-crop
  embeddings and optional vehicle constraints on identical query/gallery splits.
- If collecting an external set, consent and an example target are 30 distinct
  damage instances with 3–5 photos each. This is a proposed small pilot, not a
  statistical guarantee. Report actual counts and uncertainty; do not create
  unsafe situations or damage vehicles to collect data.

## Where the earlier papers fit

The motor-insurance network paper and critical case study remain relevant to
claims relationships. PC-GNN/CARE-GNN address graph learning problems in other
fraud domains. G-GBM's released insurance graph concerns underwriting. They are
background or a separate graph experiment, not evidence that your current app
can identify fraud. Start with the directly relevant damage-similarity paper for
the recommended scope.

## Team deliverables

| Owner | Concrete output |
|---|---|
| Data owner | Access/license check, source manifest, identity-aware splits and hard negatives |
| Vision owner | Whole-image versus crop retrieval predictions, model/checkpoint provenance |
| App owner | Historical candidate comparison, evidence persistence, reviewer outcome capture |
| Evaluation/report owner | Shared metrics script, ablations, error examples, limitations and demo |

Do not use a weighted hand-written fraud formula. A learned fraud classifier
needs appropriate outcome labels. Until those exist, deliver a narrower learned
match task and evidence-backed investigation aid that you can honestly evaluate.
