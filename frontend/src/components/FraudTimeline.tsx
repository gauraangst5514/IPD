export interface EvidenceCheck {
  id: string;
  status: "passed" | "flagged" | "inconclusive" | "unavailable" | "not_applicable";
  detail: string;
  method: string;
}

const names: Record<string, string> = {
  exif: "Photo metadata", ela: "Compression consistency", duplicate: "Exact photo reuse",
  vehicle_make: "Vehicle make", description: "Description consistency", severity: "Severity consistency", plate: "Registration plate",
};

export default function FraudTimeline({ fraudScore, checks }: { fraudScore: number | null; checks: EvidenceCheck[] }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Review signal score: {fraudScore === null ? "Unavailable" : `${(fraudScore * 100).toFixed(0)}/100`}.
        This heuristic score is not a probability of fraud.
      </p>
      {!checks.length && <p className="text-sm text-slate-500">Check results are unavailable. No verification is implied.</p>}
      <ul className="space-y-3">
        {checks.map((check) => (
          <li key={check.id} className="rounded-lg border border-slate-200 p-3">
            <div className="flex justify-between gap-3">
              <span className="font-medium">{names[check.id] || check.id}</span>
              <span className={`text-sm capitalize ${check.status === "flagged" ? "text-amber-700" : check.status === "passed" ? "text-emerald-700" : "text-slate-500"}`}>
                {check.status.split("_").join(" ")}
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">{check.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
