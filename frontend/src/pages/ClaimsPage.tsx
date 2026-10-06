import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { FileText, ArrowRight } from "lucide-react";

interface Claim {
  id: string;
  status: string;
  damage_type: string | null;
  severity: string | null;
  estimated_cost_min: number | null;
  estimated_cost_max: number | null;
  fraud_risk_score: number | null;
  created_at: string;
  image_count: number;
}

const statusColors: Record<string, string> = {
  submitted: "bg-gray-100 text-gray-700",
  processing_failed: "bg-red-100 text-red-700",
  partial_processing: "bg-orange-100 text-orange-700",
  processing: "bg-blue-100 text-blue-700",
  awaiting_review: "bg-yellow-100 text-yellow-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  flagged: "bg-orange-100 text-orange-700",
};

export default function ClaimsPage() {
  const { data: claims, isLoading } = useQuery({
    queryKey: ["claims"],
    queryFn: () => api.get<Claim[]>("/claims").then((r) => r.data),
  });

  if (isLoading) {
    return <div className="animate-pulse text-gray-500">Loading claims...</div>;
  }

  if (!claims?.length) {
    return (
      <div className="text-center py-16">
        <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">No claims yet</h2>
        <p className="text-gray-500 mt-1">File your first claim to get started.</p>
        <Link
          to="/claims/new"
          className="inline-block mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          File New Claim
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">My Claims</h1>
        <Link
          to="/claims/new"
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700"
        >
          + New Claim
        </Link>
      </div>

      <div className="space-y-3">
        {claims.map((claim) => (
          <Link
            key={claim.id}
            to={`/claims/${claim.id}`}
            className="block bg-white border border-gray-200 rounded-xl p-5 hover:border-primary-300 transition-colors"
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      statusColors[claim.status] || "bg-gray-100"
                    }`}
                  >
                    {claim.status.replace("_", " ")}
                  </span>
                  {claim.severity && (
                    <span className="text-xs text-gray-500 capitalize">
                      {claim.severity} {claim.damage_type}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">
                  Filed {new Date(claim.created_at).toLocaleDateString()} •{" "}
                  {claim.image_count} images
                </p>
                {claim.estimated_cost_min && (
                  <p className="text-sm font-medium text-gray-900 mt-1">
                    Estimated: ₹{claim.estimated_cost_min.toLocaleString()} – ₹
                    {claim.estimated_cost_max?.toLocaleString()}
                  </p>
                )}
              </div>
              <ArrowRight className="w-4 h-4 text-gray-400" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
