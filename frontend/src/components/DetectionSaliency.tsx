import { useState } from "react";
import api from "../lib/api";
type Result = {available: boolean; image_data_url?: string; reason?: string; warning?: string; target?: {label: string; confidence: number}};
export default function DetectionSaliency({imageId}: {imageId: string}) {
  const [result,setResult] = useState<Result>();
  const [busy,setBusy] = useState(false);
  async function explain() {
    setBusy(true);
    try {setResult((await api.post("/intelligence/images/"+imageId+"/saliency")).data);}
    catch {setResult({available:false,reason:"Saliency unavailable. Check the ML service and damage model; this computation may take a minute."});}
    finally {setBusy(false);}
  }
  return <div className="p-4 border-t space-y-2">
    <button disabled={busy} onClick={() => void explain()} className="border rounded px-3 py-2 text-sm disabled:opacity-50">
      {busy ? "Computing sensitivity…" : "Explain detection with occlusion saliency"}
    </button>
    <p className="text-xs text-slate-500">Masks 16 image regions and reruns the active damage detector. This explains model sensitivity, not photo authenticity.</p>
    {result?.available ? <>
      <p className="text-sm">Target: {result.target?.label} · original confidence {((result.target?.confidence || 0)*100).toFixed(1)}%</p>
      <img src={result.image_data_url} alt="Occlusion saliency: red intensity shows confidence loss when a region is masked" className="max-h-96 mx-auto"/>
      <p className="text-xs">{result.warning}</p>
    </> : result && <p role="status" className="text-amber-700 text-sm">{result.reason}</p>}
  </div>;
}
