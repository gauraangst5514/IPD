# Research results and interpretation

These are prototype measurements, not insurer validation or claims of a new architecture. Result JSON files retain protocols and per-query evidence. Raw datasets and model archives are provisioned separately.

## Closed-set encoder comparison

The downloaded Generali test subset contains 420 photographs with 39 filename-prefix identities. Each eligible image queries the remaining gallery; self-matches and exact duplicates are excluded. No target-domain fine-tuning or threshold selection is applied. Identity semantics and pretrained-training overlap have not been independently audited.

| Frozen encoder | Recall@1 | Recall@5 | mAP |
|---|---:|---:|---:|
| ImageNet ResNet18 | 90.48% | 93.81% | 58.67% |
| Released Generali OSNet-AIN | 95.24% | 98.57% | 74.82% |

Paired identity-cluster bootstrap (2,000 replicates, seed 42): Recall@1 delta +4.76 percentage points, 95% interval +1.88 to +8.08; mAP delta +16.15 points, interval +11.85 to +21.11. These intervals do not rule out training overlap or dataset shortcuts. The authors describe 385 test images, whereas this downloaded subset has 420, so this is not a verified reproduction of their full protocol.

Reports: `research/results/generali_resnet18.json`, `generali_osnet.json`, `osnet_vs_resnet.json`.

## Edited-photo reuse

113 unique TQVCD public-example sources; 28 validation sources and 85 test sources. Four transformations per test source (JPEG quality 35, brightness 0.65, 20% crop, horizontal reflection) create 340 queries against a 113-image gallery. Exact duplicate sources are grouped before splitting.

| Encoder | Recall@1 | Recall@5 |
|---|---:|---:|
| dHash | 68.82% | 76.47% |
| ResNet18 | 100% | 100% |

This tests edits of a photograph, not new views of the same physical damage. It does not establish fraud accuracy. Report: `reuse_benchmark.json`.

## Reranking: completed negative results

Both experiments use disjoint galleries for 10 validation and 29 test identities, two deterministic queries per identity, and top-five reranking. Their candidate ranking is **ResNet18**, not OSNet. Validation chooses alpha from {0, .025, .05, .1, .2, .4}; ties prefer zero/smaller weights.

| Method | Selected alpha | Test queries | Baseline Recall@1 | Selected Recall@1 |
|---|---:|---:|---:|---:|
| cosine + SIFT/RANSAC inlier term | 0 | 58 | 82.76% | 82.76% |
| cosine + LightGlue match-count term | 0 | 58 | 82.76% | 82.76% |

The LightGlue run completed all 78 queries/390 pairs in 212.36 seconds, extracting features for 256 unique photographs. Configuration: 256 SuperPoint keypoints and a real maximum edge of 640; the extractor's implicit 1024 upscale is disabled. Every validation alpha tied at 90% Recall@1. Test truncated MRR@5 is 83.76% for baseline and selected method. A [0,0] bootstrap delta is mechanical because alpha=0 selects the same ranking.

No reranking improvement is demonstrated. These numbers use a different gallery/query protocol from the 420-image encoder comparison and must not be directly compared to it. Reports: `reranking_evaluation.json`, `lightglue_reranking_evaluation.json`.

## Damage evidence pilot

Eight deterministic queries and three candidates each give 24 pairs. Both images have detected damage in 12 pairs; an equal-area non-overlapping background control exists for five pairs. Results are mixed. Masking changes the query only, using mean RGB and one highest-confidence damage rectangle. At most 100 returned correspondences are inspected. This demonstrates diagnostic feasibility/coverage, not causality, calibration or retrieval improvement. Report: `damage_evidence_pilot.json`.

## Original no-match threshold stress test

Separate 10-identity validation and 29-identity test galleries contain 121/299 images. For no-match queries, all same-identity gallery images are removed. A validation 95th-percentile maximum-impostor threshold is frozen.

| Encoder | Accepted-match coverage | Precision among accepted | No-match false alerts |
|---|---:|---:|---:|
| ResNet18 | 89.63% | 94.78% | 32.78% |
| OSNet-AIN | 94.65% | 97.53% | 38.46% |

The threshold fails to transfer. Gallery size/hard negatives differ, and the validation set is small. Report: `abstention_evaluation.json`.

## Fixed-gallery abstention continuation

A fixed gallery uses 10 identities with at least three photographs each; two photographs per identity are held out as matched queries. Nineteen separate unknown identities calibrate a finite-sample upper-tail threshold from each identity's maximum over two queries. Ten other unknown identities test it. Thresholds are never selected on test results. Too few calibration groups produce an infinite threshold, not an unsupported interpolated percentile.

At the 5% target operating point:

| Encoder | Matched acceptance | Precision among accepted | Unknown-group alerts | One-sided 95% upper bound |
|---|---:|---:|---:|---:|
| ResNet18 | 50% | 100% | 0/10 | 25.89% |
| OSNet-AIN | 90% | 100% | 1/10 | 39.42% |

This improves the protocol's control of gallery changes, but **does not establish reliable 5% abstention**. The groups must be exchangeable for a conformal interpretation; filename identity semantics and training overlap remain unverified. Report: `fixed_gallery_abstention_evaluation.json`.

## External-source stress

The 113 unique public TQVCD examples are checked against pinned Git blob hashes and tested against the fixed Generali gallery. No exact SHA-256 overlap is found. At the frozen 5% operating point, both encoders produce zero apparent alerts. This is not an independently validated false-positive rate: no cross-source physical-identity audit or matching same-damage labels exist, and repeated views may remain dependent. Report: `external_stress_evaluation.json`.

Full CarDD/CDDM access and independent same-damage evaluation remain open. See [data access](DATA_ACCESS_AND_VALIDATION.md).

## Separate structured-data experiments

A 1,000-row public-repository CSV contains 247 positive and 753 negative labels. It has no authentic pairing with these photographs. A split-first 599/200/201 train/validation/test experiment uses seven fields; unverified IDs are excluded.

| Model | Held-out records | Average precision | ROC-AUC | Brier |
|---|---:|---:|---:|---:|
| L2 logistic baseline | 201 | 0.6695 | 0.8785 | 0.1200 |
| Feature-neighbour GraphSAGE | 201 | 0.7245 | 0.9008 | 0.1004 |

These are single-split exploratory results, not new multi-seed external validation. Thresholds are selected on validation; graph edges are feature neighbours, not verified collusion links. Reports: `docs/TABULAR_EVALUATION.json`, `docs/GRAPH_EVALUATION.json`.

## What can be claimed

A working local evidence-review prototype, published pretrained models, reproducible comparison protocols, persistent photograph evidence and documented positive/negative results. A novel method outperforming OSNet, reliable abstention, fraud probability calibration, detector/cost accuracy and independent insurer generalization are not established.
