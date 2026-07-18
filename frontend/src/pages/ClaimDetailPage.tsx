import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { AlertTriangle, CheckCircle, XCircle, Thermometer } from "lucide-react";

export default function ClaimDetailPage() {
  const { id } = useParams();

  const { data: claim, isLoading } = useQuery({
    queryKey: ["claim", id],
    queryFn: () => api.get(`/claims/${id}`).then((r) => r.data),
  });

  if (isLoading) {
    return <div className="animate-pulse text-gray-500">Loading claim details...</div>;
  }

  if (!claim) {
    return <div className="text-red-600">Claim not found</div>;
  }

  const fraudLevel =
    claim.fraud_risk_score > 0.7 ? "high" : claim.fraud_risk_score > 0.3 ? "medium" : "low";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claim Details</h1>
          <p className="text-sm text-gray-500">ID: {claim.id}</p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${
            claim.status === "approved"
              ? "bg-green-100 text-green-700"
              : claim.status === "rejected"
              ? "bg-red-100 text-red-700"
              : claim.status === "flagged"
              ? "bg-orange-100 text-orange-700"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {claim.status.replace("_", " ")}
        </span>
      </div>

      {/* AI Assessment Results */}
      {claim.damage_type && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">AI Assessment</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-500">Damage Type</p>
              <p className="text-lg font-medium capitalize">{claim.damage_type}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Severity</p>
              <p className="text-lg font-medium capitalize">{claim.severity}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Confidence</p>
              <p className="text-lg font-medium">
                {((claim.confidence_score || 0) * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Cost Estimate */}
      {claim.estimated_cost_min && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">💰 Cost Estimate</h2>
          <p className="text-3xl font-bold text-gray-900">
            ₹{claim.estimated_cost_min.toLocaleString()} – ₹
            {claim.estimated_cost_max?.toLocaleString()}
          </p>
          {claim.cost_breakdown && (
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Parts</p>
                <p className="font-medium">₹{claim.cost_breakdown.parts?.toLocaleString()}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Labour</p>
                <p className="font-medium">₹{claim.cost_breakdown.labour?.toLocaleString()}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Paint</p>
                <p className="font-medium">₹{claim.cost_breakdown.paint?.toLocaleString()}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fraud Score */}
      {claim.fraud_risk_score !== null && (
        <div
          className={`border rounded-xl p-6 ${
            fraudLevel === "high"
              ? "bg-red-50 border-red-200"
              : fraudLevel === "medium"
              ? "bg-yellow-50 border-yellow-200"
              : "bg-green-50 border-green-200"
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {fraudLevel === "high" ? (
              <AlertTriangle className="w-5 h-5 text-red-600" />
            ) : fraudLevel === "medium" ? (
              <Thermometer className="w-5 h-5 text-yellow-600" />
            ) : (
              <CheckCircle className="w-5 h-5 text-green-600" />
            )}
            <h2 className="text-lg font-semibold">Fraud Risk: {fraudLevel.toUpperCase()}</h2>
          </div>
          <p className="text-sm">Score: {(claim.fraud_risk_score * 100).toFixed(1)}%</p>
          {claim.fraud_flags && Object.keys(claim.fraud_flags).length > 0 && (
            <div className="mt-2 space-y-1">
              {Object.entries(claim.fraud_flags).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2 text-sm">
                  {value ? (
                    <XCircle className="w-4 h-4 text-red-500" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  )}
                  <span className="capitalize">{key.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Images with Heatmaps */}
      {claim.images?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Images & Heatmaps</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {claim.images.map((img: { id: string; original_url: string; heatmap_url: string | null; damage_type: string | null; severity: string | null; confidence: number | null }) => (
              <div key={img.id} className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="aspect-video bg-gray-100 flex items-center justify-center">
                  <img
                    src={img.original_url}
                    alt="Claim"
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                </div>
                {img.heatmap_url && (
                  <div className="aspect-video bg-gray-100">
                    <img
                      src={img.heatmap_url}
                      alt="Heatmap"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
                <div className="p-3 text-sm">
                  <p className="capitalize">
                    {img.damage_type} • {img.severity} • {((img.confidence || 0) * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
