import { AlertTriangle, Info } from "lucide-react";
import { Link } from "react-router-dom";

interface EvidenceMatch {
  claim_id: string;
  image_id: string;
  match_type: string;
  phash_distance: number;
  dhash_distance: number;
}
interface EvidenceIndicator {
  code: string;
  status: "review" | "not_observed" | "unavailable" | "informational";
  detail: string;
  image_id?: string;
  evidence?: { matches?: EvidenceMatch[] };
}
interface FraudTimelineProps {
  fraudFlags: Record<string, unknown>;
}

/** Display observed evidence without turning absence of a flag into a pass. */
export default function FraudTimeline({ fraudFlags }: FraudTimelineProps) {
  const indicators = Array.isArray(fraudFlags._indicators)
    ? (fraudFlags._indicators as EvidenceIndicator[])
    : [];
  const needsReview = indicators.some((item) => item.status === "review");
  const incomplete = indicators.some((item) => item.status === "unavailable");

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        {needsReview ? "Evidence requires review." : "No review indicator recorded."}
        {" "}Fraud probability has not been estimated.
      </p>
      {incomplete && (
        <p className="text-sm text-amber-700">Some checks are unavailable. Missing evidence does not establish fraud or genuineness.</p>
      )}
      {indicators.length === 0 ? (
        <p className="text-sm text-slate-500">Reprocess this claim to generate evidence indicators. Legacy risk percentages are not validated fraud probabilities.</p>
      ) : (
        <ul className="space-y-3">
          {indicators.map((item, index) => (
            <li key={`${item.image_id || "claim"}-${item.code}-${index}`}
              className="border border-slate-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                {item.status === "review" ? (
                  <AlertTriangle aria-hidden="true" className="w-4 h-4 text-amber-600" />
                ) : (
                  <Info aria-hidden="true" className="w-4 h-4 text-slate-400" />
                )}
                <span className="text-sm font-medium capitalize">{item.code.replace(/_/g, " ")}</span>
                <span className="text-xs text-slate-500">{item.status.replace(/_/g, " ")}</span>
              </div>
              <p className="text-sm text-slate-600 mt-1">{item.detail}</p>
              {item.image_id && <p className="text-xs text-slate-400 mt-1">Image: {item.image_id}</p>}
              {item.evidence?.matches?.map((match) => (
                <p key={`${match.claim_id}-${match.image_id}`} className="text-xs mt-2">
                  <Link className="text-primary-600 underline" to={`/claims/${encodeURIComponent(match.claim_id)}`}>
                    View matching claim {match.claim_id}
                  </Link>
                  {" · "}{match.match_type === "exact_file" ? "Identical file" : "Candidate visual match"}
                  {" · "}hash distances {match.phash_distance}/{match.dhash_distance}
                </p>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
