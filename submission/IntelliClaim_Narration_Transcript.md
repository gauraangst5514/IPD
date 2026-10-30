# Narrated walkthrough

Edited from actual browser screen captures, with synthesized Aman narration. This is not a continuous screen recording.

1. Available investigator checks

The dashboard reports the checks that are actually installed. Vehicle make verification, plate OCR, TruFor forensic diagnostics, and historical photograph retrieval are now available. These are research aids for an investigator, and do not establish fraudulent intent.

2. Historical photograph retrieval

Photo retrieval is restricted to assessors and administrators. The gallery shown here is a local research demonstration gallery. It is separate from the claim database and from the frozen offline evaluation corpus.

3. Select an original photograph

Select a photograph and choose three, five, or ten candidates. The application sends the bytes through the authenticated backend to the pretrained OSNet embedding model. The query preview helps the assessor confirm the selected evidence.

4. Review ranked evidence

The model ranks historical photographs by cosine similarity. Similarity is not a probability. The cards include local feature counts and damage-region diagnostics. An unavailable detector result remains explicit instead of being replaced with an invented score.

5. Inspect matching local features

Expand correspondence inspection to see keypoints and connecting lines between the query and a candidate. Coordinates are scaled to the rendered photographs. Matches may come from background or undamaged bodywork, so they do not prove the same physical damage.

6. Compare without overlays

The line toggle hides the overlay so the photographs can be inspected directly. Damage masking measures sensitivity to an artificial perturbation. It does not establish a causal explanation, image authenticity, or an automatic insurance decision.

7. Index history and retain limitations

Assessors can add photographs to the historical gallery. Exact duplicates are detected, and images survive a restart. The completed LightGlue experiment showed no improvement. Abstention and external sample tests are documented with uncertainty, and the final decision stays with the human investigator.