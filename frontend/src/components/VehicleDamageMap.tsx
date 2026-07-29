import { useState } from "react";

interface Detection {
  label: string;
  confidence: number;
  bbox: number[];
}

interface VehicleDamageMapProps {
  detections: Detection[];
  severity: string;
}

// Damage type metadata
const DAMAGE_INFO: Record<string, { icon: string; color: string; bg: string; description: string }> = {
  dent: { icon: "⊘", color: "text-orange-700", bg: "bg-orange-100", description: "Panel deformation from impact" },
  scratch: { icon: "⁄", color: "text-yellow-700", bg: "bg-yellow-100", description: "Surface paint damage" },
  crack: { icon: "⚡", color: "text-red-700", bg: "bg-red-100", description: "Structural fracture or split" },
  glass_shatter: { icon: "◇", color: "text-blue-700", bg: "bg-blue-100", description: "Windshield or window damage" },
  lamp_broken: { icon: "◉", color: "text-purple-700", bg: "bg-purple-100", description: "Headlight or taillight damage" },
  tire_flat: { icon: "○", color: "text-slate-700", bg: "bg-slate-100", description: "Tire puncture or blowout" },
};

const SEVERITY_CONFIG = {
  minor: { label: "Minor", color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200", bar: "bg-amber-400", pct: 33 },
  moderate: { label: "Moderate", color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200", bar: "bg-orange-500", pct: 66 },
  severe: { label: "Severe", color: "text-red-600", bg: "bg-red-50", border: "border-red-200", bar: "bg-red-500", pct: 100 },
};

export default function VehicleDamageMap({ detections, severity }: VehicleDamageMapProps) {
  const [hoveredType, setHoveredType] = useState<string | null>(null);

  // Group detections by type
  const grouped = new Map<string, { count: number; maxConf: number; totalArea: number }>();
  for (const det of detections) {
    const existing = grouped.get(det.label);
    const area = det.bbox[2] * det.bbox[3]; // width * height (normalized)
    if (existing) {
      existing.count += 1;
      existing.maxConf = Math.max(existing.maxConf, det.confidence);
      existing.totalArea += area;
    } else {
      grouped.set(det.label, { count: 1, maxConf: det.confidence, totalArea: area });
    }
  }

  const sevConfig = SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.moderate;

  return (
    <div className="space-y-5">
      {/* Severity indicator */}
      <div className={`flex items-center justify-between p-4 rounded-lg border ${sevConfig.border} ${sevConfig.bg}`}>
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Overall Severity</p>
          <p className={`text-xl font-bold mt-0.5 ${sevConfig.color}`}>{sevConfig.label}</p>
        </div>
        <div className="w-32">
          <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${sevConfig.bar}`}
              style={{ width: `${sevConfig.pct}%` }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[9px] text-slate-400">Low</span>
            <span className="text-[9px] text-slate-400">Critical</span>
          </div>
        </div>
      </div>

      {/* Damage type breakdown */}
      <div>
        <p className="text-sm font-medium text-slate-700 mb-3">Detected Damage Types</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[...grouped.entries()].sort((a, b) => b[1].maxConf - a[1].maxConf).map(([type, data]) => {
            const info = DAMAGE_INFO[type] || { icon: "•", color: "text-slate-700", bg: "bg-slate-100", description: "Damage detected" };
            const isHovered = hoveredType === type;

            return (
              <div
                key={type}
                className={`relative p-4 rounded-lg border transition-all duration-150 cursor-default ${
                  isHovered ? "border-primary-300 shadow-md" : "border-slate-200"
                }`}
                onMouseEnter={() => setHoveredType(type)}
                onMouseLeave={() => setHoveredType(null)}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-lg ${info.bg} flex items-center justify-center text-lg flex-shrink-0`}>
                    {info.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className={`text-sm font-semibold capitalize ${info.color}`}>
                        {type.replace("_", " ")}
                      </p>
                      <span className="text-xs font-mono text-slate-500">
                        ×{data.count}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{info.description}</p>

                    {/* Confidence bar */}
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary-500 transition-all duration-500"
                          style={{ width: `${data.maxConf * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-medium text-slate-600 w-8 text-right">
                        {(data.maxConf * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Area indicator */}
                <div className="mt-2 text-[10px] text-slate-400">
                  Coverage: {(data.totalArea * 100).toFixed(1)}% of image
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary stats */}
      <div className="flex items-center gap-6 pt-3 border-t border-slate-100 text-xs text-slate-500">
        <span><strong className="text-slate-700">{detections.length}</strong> damage instances detected</span>
        <span><strong className="text-slate-700">{grouped.size}</strong> damage types</span>
        <span>
          Total area: <strong className="text-slate-700">
            {(detections.reduce((sum, d) => sum + d.bbox[2] * d.bbox[3], 0) * 100).toFixed(1)}%
          </strong>
        </span>
      </div>
    </div>
  );
}
