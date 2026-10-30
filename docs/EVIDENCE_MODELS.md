# Installed photograph evidence models

The dashboard reports model availability separately from whether a particular photograph supports a conclusion.

| Check | Implemented model/method | Scope |
|---|---|---|
| Vehicle verification | `nenzilea/car-classification`, revision `40b07a61c3125b0be2e607efe6581d4e64c8b801`, Apache-2.0 model card; local safetensors only | Nine makes: BMW, Dodge, Ferrari, Ford, Jeep, Lamborghini, Porsche, Rolls-Royce, Toyota. Unsupported makes and low-score damage close-ups are inconclusive. Softmax values are uncalibrated. |
| Registration OCR | EasyOCR 1.7.2 CRAFT + English generation-2 weights | English text and Indian-registration patterns; confidence-gated candidates. O/Q/I/Z/S/B digit-position confusions are recorded as normalization, with raw OCR retained. No readable plate is inconclusive. Runtime downloads are disabled. |
| Photograph tampering | Official pretrained [TruFor](https://github.com/grip-unina/TruFor) | Whole-image model score, localization map and reliability summary. Inputs are bounded to a 768-pixel edge and use the authors' `/256` normalization. No calibrated authenticity or insurance fraud probability is claimed. **Informational/nonprofit research use only** under the retained upstream license. |
| Historical damage-photo matching | Released Generali OSNet-AIN + local correspondences | Candidate retrieval, with explicit human review. It does not establish the same physical damage. |

TruFor source notices and upstream licenses are under `ml/vendor/trufor/`. `PROVENANCE.json` records the pinned source revision and the official weight archive checksum. The legacy checkpoint is converted with a narrow pickle-global allowlist to a pure tensor state and then loaded strictly with `weights_only=True`. Vehicle weights use safetensors with `local_files_only=True` and no remote model code.

Provisioning command: `.venv/bin/python scripts/provision_evidence_models.py`. It runs at setup/container-build time, not in an upload request.

An assessor can open a claim photograph and select **Inspect vehicle, plate, tampering and history**. The panel exposes real per-photo model outputs, including inconclusive results, forensic localization and gallery candidates. The authenticated API proxy is `POST /api/v1/intelligence/images/{image_id}/evidence`; the ML service remains private in the Vercel service configuration.

A positive synthetic OCR fixture read `MH02AB1234`; a real vehicle-photo smoke returned a low-confidence make suggestion and remained inconclusive; TruFor produced a finite model score and map. These are integration checks, not measured accuracy or calibration on real insurance outcomes.
