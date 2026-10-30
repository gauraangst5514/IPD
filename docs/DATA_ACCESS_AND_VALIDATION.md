# External data access and validation

Checked against the official sources on 30 October 2026.

| Source | Actual access | Next requirement | What it can validate |
|---|---|---|---|
| [CarDD](https://cardd-ustc.github.io/) | Full dataset not acquired | Complete the [official licensing form](https://cardd-ustc.github.io/docs/CarDD_license.pdf), sign it yourself and obtain an author-issued download link | Damage detection/localization; not by itself a same-physical-damage retrieval benchmark |
| [CDDM](https://github.com/SCUT-CCNL/CDDM) | Full paired-view dataset not acquired | Complete the repository's licensing form and obtain the authors' download link | Paired distant/close views, subject to auditing pair/identity semantics and overlap |
| [TQVCD](https://github.com/dxlabskku/TQVCD) | 120 public examples, 113 exact-content-unique images locally verified against a pinned repository manifest | Full 2,300-image set is available on author request; publication/redistribution terms need explicit confirmation | External-source stress; sample labels do not establish physical-damage identities |

A user's approval to research or use a dataset does not supply an author-issued access grant or a missing signature. No request has been sent to dataset authors and no licensing form has been signed on the user's behalf. Unofficial mirrors were not treated as permission to redistribute a restricted dataset.

## Completed external-source stress test

`research/results/external_stress_evaluation.json` records frozen-gallery tests on the 113 unique public TQVCD photographs. Every local sample file was checked against its Git blob SHA, and no SHA-256 overlaps with the 420 Generali benchmark photographs were found. Neither encoder produced an apparent alert at its frozen 5% operating point. This is not a validated false-positive rate: cross-source physical identity disjointness and independence remain assumptions, and there are no matching same-damage labels.

## Improved abstention protocol

`research/results/fixed_gallery_abstention_evaluation.json` fixes one gallery, assigns 19 independent filename-identity groups to calibration, and holds out 10 other unknown groups for testing. Two queries per identity are used, with the maximum per calibration identity as the calibration unit. Gallery identities require at least three photographs so two held-out matched queries remain separate from gallery images. A finite-sample upper-tail order statistic replaces an interpolated percentile; an undersized calibration set returns an infinite threshold rather than implying unsupported precision. Test data never selects a threshold.

At the 5% operating point, OSNet accepts 90% of the matched queries, with 100% precision among those accepted, but alerts on 1/10 unknown identity groups. Its one-sided 95% upper bound is 39.42%, so reliable 5% rejection is **not established**. ResNet has 0/10 unknown group alerts with a 25.89% upper bound and 50% matched acceptance. These are different protocols from the earlier split-specific-gallery stress test; their numbers are not directly comparable. An automatic insurance or fraud decision remains disabled.

## Draft access request — not sent

Subject: Academic research access request for [CarDD/CDDM]

Dear dataset authors,

I am developing IntelliClaim, a nonprofit research prototype for vehicle-damage evidence review. I would like to evaluate a published pretrained detector/retrieval baseline on an independent, licensed test set. We report uncertainty and negative results, retain human investigation, and do not interpret similarity as fraudulent intent.

Please advise on academic access, allowed model evaluation and publication, identity/pair semantics, and whether derived metrics or example screenshots may be included in a research report. I will complete your licensing form with my name, affiliation and signature.

Name: [user to complete]
Affiliation: [user to complete]
Research contact: [user to complete]

No raw dataset or credentials will be published without the applicable permission.
