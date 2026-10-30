import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";

interface Capabilities {
  status: string;
  components: Record<string, { available: boolean; method?: string; limitation?: string; supported_makes?: string[] }>;
}

const labels: Record<string, string> = {
  damage_detection: "Damage assessment",
  image_reuse: "Photograph reuse",
  text_consistency: "Text consistency",
  vehicle_make: "Vehicle verification",
  tamper_detection: "Photograph tampering",
  damage_reidentification: "Historical damage-photo matching",
  saliency: "Model saliency maps",
  tabular_classifier: "Tabular research classifier",
  graph_baseline: "GraphSAGE research baseline",
  plate_reader: "Registration-plate OCR",
};

export default function ComponentStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<Capabilities>("/capabilities").then((response) => response.data),
    refetchInterval: 30000,
    retry: 1,
  });
  return (
    <section className="card p-5 mb-6" aria-label="Assessment availability">
      <h2 className="font-semibold text-slate-900">Assessment availability</h2>
      <p className="text-sm text-slate-500 mt-1">
        {isPending ? "Checking available assessments..." : isError || data?.status === "unreachable"
          ? "Assessment service could not be reached. Results may be unavailable."
          : "Only available assessments contribute evidence. Unavailable checks remain visible in each claim."}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
        {Object.entries(labels).map(([key, label]) => {
          const component = data?.components[key];
          return (
            <div key={key} className="rounded-lg border border-slate-200 p-3">
              <p className="text-sm font-medium">{label}</p>
              <p className={`text-xs mt-1 ${component?.available ? "text-emerald-700" : "text-slate-500"}`}>
                {isPending ? "Checking" : component?.available
                  ? key === "text_consistency" ? "Available · keyword baseline" : key === "damage_reidentification" ? "Available · candidate retrieval" : key === "tamper_detection" ? "Available · pretrained research model" : "Available"
                  : "Unavailable"}
              </p>
              {component?.limitation && <p className="text-xs text-slate-500 mt-1">{component.limitation}</p>}
              {!!component?.supported_makes?.length && <p className="text-xs text-slate-500 mt-1">{component.supported_makes.length} supported makes</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
