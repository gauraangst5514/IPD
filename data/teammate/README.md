# Teammate benchmark snapshot

Source: https://github.com/PrathamMehta101/ipd/blob/main/data/insurance_claims.csv
Retrieved 29 October 2026 via the connected GitHub service.

This is a public-repository snapshot, not an insurer-provided dataset. Original
collection provenance and redistribution licence have not been established.
Keep it within this team project until those are established. It has 1,000 rows
and 247 positive labels. Garage/claimant IDs have strong label alignment and are
excluded from the learned tabular model until their construction is documented.
This dataset is separate from CarDD; there is no genuine row-to-image mapping.

The new split-first logistic baseline adapts the teammate's selected seven
features. Existing leaky XGBoost/GNN binary artifacts are deliberately not loaded.
