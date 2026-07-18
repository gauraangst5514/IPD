import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { AlertTriangle, ArrowRight } from "lucide-react";

export default function ReviewQueuePage() {
  const { data: claims, isLoading } = useQuery({
    queryKey: ["review-queue"],
    queryFn: () => api.get("/assessments/queue").then((r) => r.data),
  });

  if (isLoading) {
    return <div className="animate-pulse text-gray-500">Loading review queue...</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Review Queue</h1>
      <p className="text-gray-500 mb-6">
        Claims sorted by fraud risk (highest first). Review AI assessment and make a decision.
      </p>

      {!claims?.length ? (
        <div className="text-center py-16 text-gray-500">
          No claims pending review. 🎉
        </div>
      ) : (
        <div className="space-y-3">
          {claims.map((claim: {
            id: string;
            status: string;
            damage_type: string | null;
            severity: string | null;
            estimated_cost_min: number | null;
            estimated_cost_max: number | null;
            fraud_risk_score: number | null;
            created_at: string;
          }) => (
            <Link
              key={claim.id}
              to={`/claims/${claim.id}`}
              className="block bg-white border border-gray-200 rounded-xl p-5 hover:border-primary-300 transition-colors"
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-4">
                  {(claim.fraud_risk_score || 0) > 0.5 && (
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium text-gray-900 capitalize">
                      {claim.severity} {claim.damage_type || "damage"}
                    </p>
                    <p className="text-sm text-gray-500">
                      {new Date(claim.created_at).toLocaleDateString()}
                      {claim.estimated_cost_min &&
                        ` • ₹${claim.estimated_cost_min.toLocaleString()}–₹${claim.estimated_cost_max?.toLocaleString()}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {claim.fraud_risk_score !== null && (
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        claim.fraud_risk_score > 0.7
                          ? "bg-red-100 text-red-700"
                          : claim.fraud_risk_score > 0.3
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      Risk: {(claim.fraud_risk_score * 100).toFixed(0)}%
                    </span>
                  )}
                  <ArrowRight className="w-4 h-4 text-gray-400" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
