import { useState } from 'react';
import api from '../lib/api';

type Result = {
  vehicle_make: { match: boolean | null; detected_make?: string; confidence?: number; detail?: string };
  plate: { detected_plates: string[]; match: boolean | null; detail?: string; normalization?: string };
  tamper: { available: boolean; model_score?: number; localization_data_url?: string; limitation?: string; reason?: string };
  historical_photographs: { candidates: { image_id: string; thumbnail: string; cosine_similarity: number }[] };
};

export default function PhotoEvidenceInspector({ imageId }: { imageId: string }) {
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function inspect() {
    setBusy(true); setError('');
    try {
      const response = await api.post<Result>(`/intelligence/images/${imageId}/evidence`, undefined, { timeout: 240000 });
      setResult(response.data);
    } catch { setError('Photograph evidence could not complete. Please retry.'); }
    finally { setBusy(false); }
  }
  return <section className="mt-3 space-y-3 border-t pt-3" aria-label="Photograph evidence inspection">
    <button type="button" className="btn-secondary text-xs" disabled={busy} onClick={inspect}>
      {busy ? 'Inspecting photograph…' : 'Inspect vehicle, plate, tampering and history'}
    </button>
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
    {result && <div className="space-y-3 text-sm" aria-live="polite">
      <div><h4 className="font-semibold">Vehicle make</h4>
        <p>{result.vehicle_make.detected_make ?? 'Inconclusive'}{result.vehicle_make.confidence != null ? ` · model score ${result.vehicle_make.confidence.toFixed(3)}` : ''}</p>
        {result.vehicle_make.detail && <p className="text-xs text-slate-500">{result.vehicle_make.detail}</p>}
      </div>
      <div><h4 className="font-semibold">Registration plate</h4>
        <p>{result.plate.detected_plates.join(', ') || 'No readable plate · inconclusive'}</p>
        {result.plate.normalization && <p className="text-xs text-slate-500">{result.plate.normalization}</p>}
      </div>
      <div><h4 className="font-semibold">TruFor forensic diagnostics</h4>
        <p>{result.tamper.available && result.tamper.model_score != null ? `Uncalibrated model score: ${result.tamper.model_score.toFixed(3)}` : 'Unavailable for this photograph'}</p>
        {result.tamper.localization_data_url && <img src={result.tamper.localization_data_url} alt="TruFor predicted manipulation localization; red indicates higher model response" className="max-h-48 rounded" />}
        <p className="text-xs text-slate-500">{result.tamper.limitation}</p>
      </div>
      <div><h4 className="font-semibold">Historical photograph candidates</h4>
        <div className="grid grid-cols-3 gap-2 mt-2">{result.historical_photographs.candidates.map(candidate => <figure key={candidate.image_id}>
          <img src={candidate.thumbnail} alt={`Historical photograph ${candidate.image_id}`} className="h-24 w-full object-contain bg-slate-100" />
          <figcaption className="text-xs break-all">{candidate.image_id} · {candidate.cosine_similarity.toFixed(3)}</figcaption>
        </figure>)}</div>
        {!result.historical_photographs.candidates.length && <p>No indexed history yet. Add claim photographs to the gallery.</p>}
      </div>
      <p className="text-xs text-slate-500">These are investigator aids. Model scores are not fraud probabilities, and candidate matches do not prove the same physical damage.</p>
    </div>}
  </section>;
}
