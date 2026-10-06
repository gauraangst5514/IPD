import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import api from "../lib/api";
import { Download } from "lucide-react";
import ClaimImageView from "../components/ClaimImageView";
import AssessmentForm from "../components/AssessmentForm";
import FraudTimeline from "../components/FraudTimeline";
import VehicleDamageMap from "../components/VehicleDamageMap";

export default function ClaimDetailPage() {
  const { id } = useParams();
  const role = useAuthStore((state) => state.role);
  const userId = useAuthStore((state) => state.userId);
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => api.post(`/claims/${id}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claim", id] });
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });

  const { data: claim, isLoading } = useQuery({
    queryKey: ["claim", id],
    queryFn: () => api.get(`/claims/${id}`).then((r) => r.data),
    refetchInterval: (query) => query.state.data?.status === "processing" ? 3000 : false,
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
            {claim.status.split("_").join(" ")}
          </span>
        </div>
      </div>

      {(claim.status === "processing_failed" || claim.status === "partial_processing") && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5" role="status">
          <p className="font-medium">{claim.status === "processing_failed" ? "Image analysis could not be completed." : "Some images could not be analyzed. Results below are incomplete."}</p>
          <p className="mt-1 text-sm">Retry when the analysis service is available. Complete analysis is required before review.</p>
          {claim.claimant_id === userId && (
            <button className="btn-primary mt-3" disabled={retry.isPending} onClick={() => retry.mutate()}>
              {retry.isPending ? "Requesting retry…" : "Retry analysis"}
            </button>
          )}
          {retry.isError && <p className="mt-2 text-red-700" role="alert">Retry could not be started. Refresh the claim and try again.</p>}
        </div>
      )}

      {claim.status === "processing" && <p role="status" className="rounded-xl border bg-blue-50 p-4">Assessment is queued or running. Previous results are not current while this attempt is in progress.</p>}
      {claim.analysis_outcome === "no_visible_damage" && claim.status !== "processing" && (
        <p className="rounded-xl border bg-slate-50 p-4">No visible damage was detected. No repair estimate has been generated. This does not rule out hidden damage or insufficient photo coverage.</p>
      )}
      {(role === "assessor" || role === "admin") && userId !== claim.claimant_id && ["awaiting_review", "flagged"].includes(claim.status) && (
        <AssessmentForm claimId={claim.id} version={claim.review_version} />
      )}

      {/* AI Assessment Results */}
      {claim.damage_type && claim.status !== "processing" && (
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
              <p className="text-sm text-gray-500">Detector score (uncalibrated)</p>
              <p className="text-lg font-medium">
                {claim.detector_confidence === null ? "Unavailable" : `${(claim.detector_confidence * 100).toFixed(1)}%`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Vehicle Damage Map */}
      {claim.status !== "processing" && claim.detections && claim.detections.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Damage Breakdown</h2>
          <VehicleDamageMap
            detections={claim.detections}
            severity={claim.severity || "moderate"}
          />
        </div>
      )}

      {/* Cost Estimate */}
      {claim.estimated_cost_min !== null && claim.status !== "processing" && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Provisional repair estimate</h2>
          <p className="mb-3 text-sm text-slate-600">Heuristic estimate from the highest-cost photo; separate repair operations across views are not yet reconciled.</p>
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
      {claim.status !== "processing" && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Evidence checks</h2>
          <FraudTimeline
            fraudScore={claim.fraud_risk_score}
            checks={claim.checks || []}
          />
        </div>
      )}

      {/* Images with Heatmaps */}
      {claim.images?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Damage Analysis</h2>
          <div className="grid grid-cols-1 gap-6">
            {claim.images.map((img: { id: string; original_url: string; heatmap_url: string | null; damage_type: string | null; severity: string | null; detector_confidence: number | null; processing_status: string; processing_error: string | null; annotation_error: string | null; duplicate_evidence: { match_count: number } | null }) => (
              <div key={img.id} className="border border-slate-200 rounded-lg overflow-hidden">
                <ClaimImageView original={img.original_url} annotated={claim.status === "processing" ? null : img.heatmap_url} />
                {claim.status !== "processing" && <>{img.processing_error && <p className="p-3 text-sm text-red-700">Analysis unavailable for this image. Retry the claim to analyze it again.</p>}
                {img.annotation_error && <p className="p-3 text-sm text-amber-700">Analysis completed; annotated preview is unavailable.</p>}
                {!!img.duplicate_evidence?.match_count && <p className="p-3 text-sm text-amber-700">This exact photo appears elsewhere in your uploaded images. This match alone does not establish fraud.</p>}
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
                      {img.damage_type || img.processing_status?.split("_").join(" ") || "Pending"}
                    </span>
                  </div>
                  <span className="text-sm text-slate-500">
                    {img.detector_confidence == null ? "Detector score unavailable" : `${(img.detector_confidence * 100).toFixed(0)}% detector score (uncalibrated)`}
                  </span>
                </div></>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
