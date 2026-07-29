import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { Download } from "lucide-react";
import ImageCompareSlider from "../components/ImageCompareSlider";
import FraudTimeline from "../components/FraudTimeline";
import VehicleDamageMap from "../components/VehicleDamageMap";

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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claim Details</h1>
          <p className="text-sm text-gray-500">ID: {claim.id}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              try {
                const res = await api.get(`/claims/${id}/pdf`, { responseType: "blob" });
                const url = window.URL.createObjectURL(new Blob([res.data]));
                const a = document.createElement("a");
                a.href = url;
                a.download = `claim_${claim.id.slice(0, 8)}_report.pdf`;
                a.click();
                window.URL.revokeObjectURL(url);
              } catch {
                alert("Failed to download PDF");
              }
            }}
            className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </button>
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

      {/* Vehicle Damage Map */}
      {claim.detections && claim.detections.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Damage Breakdown</h2>
          <VehicleDamageMap
            detections={claim.detections}
            severity={claim.severity || "moderate"}
          />
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
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Fraud Risk Analysis</h2>
          <FraudTimeline
            fraudScore={claim.fraud_risk_score}
            fraudFlags={claim.fraud_flags || {}}
          />
        </div>
      )}

      {/* Images with Heatmaps */}
      {claim.images?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Damage Analysis</h2>
          <div className="grid grid-cols-1 gap-6">
            {claim.images.map((img: { id: string; original_url: string; heatmap_url: string | null; damage_type: string | null; severity: string | null; confidence: number | null }) => (
              <div key={img.id} className="border border-slate-200 rounded-lg overflow-hidden">
                {img.heatmap_url ? (
                  /* Comparison slider when both images available */
                  <ImageCompareSlider
                    originalSrc={img.original_url}
                    annotatedSrc={img.heatmap_url}
                    originalLabel="Original Photo"
                    annotatedLabel="AI Detection"
                  />
                ) : (
                  /* Just the original if no heatmap */
                  <div className="bg-slate-100 p-2">
                    <img
                      src={img.original_url}
                      alt="Uploaded damage photo"
                      className="w-full h-auto max-h-[400px] object-contain rounded"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  </div>
                )}
                <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`badge ${
                      img.severity === "severe" ? "bg-red-100 text-red-700" :
                      img.severity === "moderate" ? "bg-amber-100 text-amber-700" :
                      "bg-emerald-100 text-emerald-700"
                    }`}>
                      {img.severity || "—"}
                    </span>
                    <span className="text-sm font-medium text-slate-700 capitalize">
                      {img.damage_type || "Processing"}
                    </span>
                  </div>
                  <span className="text-sm text-slate-500">
                    {((img.confidence || 0) * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
