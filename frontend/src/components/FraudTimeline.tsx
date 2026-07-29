import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Shield, AlertTriangle } from "lucide-react";

interface FraudCheck {
  id: string;
  label: string;
  status: "pass" | "fail" | "warn" | "pending";
  detail?: string;
}

interface FraudTimelineProps {
  fraudScore: number;
  fraudFlags: Record<string, boolean>;
}

/**
 * Animated fraud risk timeline that reveals checks one by one.
 */
export default function FraudTimeline({ fraudScore, fraudFlags }: FraudTimelineProps) {
  const [visibleCount, setVisibleCount] = useState(0);

  // Build checks from fraud flags
  const allChecks: FraudCheck[] = [
    {
      id: "exif",
      label: "EXIF Metadata",
      status: fraudFlags["exif_inconsistency"] ? "fail" : "pass",
      detail: fraudFlags["exif_inconsistency"] ? "Missing or suspicious metadata" : "Valid camera metadata",
    },
    {
      id: "ela",
      label: "Error Level Analysis",
      status: fraudFlags["high_ela_score"] ? "fail" : "pass",
      detail: fraudFlags["high_ela_score"] ? "Possible pixel manipulation detected" : "No manipulation detected",
    },
    {
      id: "duplicate",
      label: "Duplicate Check",
      status: fraudFlags["duplicate_image"] ? "fail" : "pass",
      detail: fraudFlags["duplicate_image"] ? "Image used in another claim" : "No duplicates found",
    },
    {
      id: "vehicle_make",
      label: "Vehicle Make Verification",
      status: fraudFlags["vehicle_make_mismatch"] ? "fail" : "pass",
      detail: fraudFlags["vehicle_make_mismatch"] ? "Vehicle doesn't match claimed make" : "Vehicle make verified",
    },
    {
      id: "description",
      label: "Description Consistency",
      status: fraudFlags["description_mismatch"] ? "warn" : "pass",
      detail: fraudFlags["description_mismatch"] ? "Description doesn't match detected damage" : "Description is consistent",
    },
    ...(fraudFlags["plate_number_mismatch"] ? [{
      id: "plate",
      label: "License Plate Check",
      status: "fail" as const,
      detail: "Plate doesn't match registration",
    }] : []),
    {
      id: "severity",
      label: "Severity Consistency",
      status: fraudFlags["severity_mismatch"] ? "warn" : "pass",
      detail: fraudFlags["severity_mismatch"] ? "Claimed severity doesn't match AI assessment" : "Severity is consistent",
    },
  ];

  // Animate checks appearing one by one
  useEffect(() => {
    if (visibleCount < allChecks.length) {
      const timer = setTimeout(() => {
        setVisibleCount((c) => c + 1);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [visibleCount, allChecks.length]);

  const fraudLevel = fraudScore > 0.7 ? "high" : fraudScore > 0.3 ? "medium" : "low";

  return (
    <div className="space-y-4">
      {/* Score gauge */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium text-slate-700">Fraud Risk Score</span>
            <span className={`text-sm font-bold ${
              fraudLevel === "high" ? "text-red-600" : fraudLevel === "medium" ? "text-amber-600" : "text-emerald-600"
            }`}>
              {(fraudScore * 100).toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                fraudLevel === "high" ? "bg-red-500" : fraudLevel === "medium" ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(100, fraudScore * 100)}%` }}
            />
          </div>
        </div>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
          fraudLevel === "high" ? "bg-red-100" : fraudLevel === "medium" ? "bg-amber-100" : "bg-emerald-100"
        }`}>
          {fraudLevel === "high" ? (
            <AlertTriangle className="w-5 h-5 text-red-600" />
          ) : fraudLevel === "medium" ? (
            <Shield className="w-5 h-5 text-amber-600" />
          ) : (
            <CheckCircle className="w-5 h-5 text-emerald-600" />
          )}
        </div>
      </div>

      {/* Checks timeline */}
      <div className="space-y-0">
        {allChecks.map((check, i) => {
          const isVisible = i < visibleCount;
          const isLast = i === allChecks.length - 1;

          return (
            <div
              key={check.id}
              className={`flex items-start gap-3 transition-all duration-300 ${
                isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
              }`}
            >
              {/* Timeline connector */}
              <div className="flex flex-col items-center">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                  check.status === "pass" ? "bg-emerald-100" :
                  check.status === "warn" ? "bg-amber-100" :
                  check.status === "fail" ? "bg-red-100" : "bg-slate-100"
                }`}>
                  {check.status === "pass" && <CheckCircle className="w-4 h-4 text-emerald-600" />}
                  {check.status === "warn" && <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
                  {check.status === "fail" && <XCircle className="w-4 h-4 text-red-600" />}
                  {check.status === "pending" && <div className="w-2 h-2 rounded-full bg-slate-300" />}
                </div>
                {!isLast && (
                  <div className={`w-px h-6 ${
                    check.status === "pass" ? "bg-emerald-200" :
                    check.status === "warn" ? "bg-amber-200" :
                    check.status === "fail" ? "bg-red-200" : "bg-slate-200"
                  }`} />
                )}
              </div>

              {/* Content */}
              <div className="pb-4 min-w-0">
                <p className="text-sm font-medium text-slate-800">{check.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{check.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
