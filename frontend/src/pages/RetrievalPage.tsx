import { useState, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Upload, Search, Eye, Layers, Info, PlusCircle, Database, CheckCircle, Loader2 } from 'lucide-react';
import api from '../lib/api';
import CorrespondenceOverlay from '../components/CorrespondenceOverlay';

interface Correspondence { query: [number, number]; candidate: [number, number] }

interface Verification {
  method: string;
  matches: number;
  inliers?: number;
  correspondences?: Correspondence[];
  query_size?: [number, number];
  candidate_size?: [number, number];
  status?: string;
}

interface DamageEvidence {
  available: boolean;
  reason?: string;
  damage_supported_correspondences?: number;
  evaluated_correspondences?: number;
  damage_mask_score_drop?: number | null;
  background_mask_score_drop?: number | null;
}

interface Candidate {
  image_id: string;
  thumbnail: string;
  cosine_similarity: number;
  verification: Verification;
  damage_evidence?: DamageEvidence;
}

interface Result {
  gallery_size: number;
  embedding: string;
  candidates: Candidate[];
}

interface GalleryStats {
  gallery_size: number;
  embedding: string | null;
  model_loaded: boolean;
  gallery_path: string;
}

export default function RetrievalPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [queryPreview, setQueryPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [kCount, setKCount] = useState<number>(5);
  const [expandedCorrespondence, setExpandedCorrespondence] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Gallery management state
  const [showAddModal, setShowAddModal] = useState(false);
  const [ingestFile, setIngestFile] = useState<File | null>(null);
  const [ingestBusy, setIngestBusy] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<{ type: 'success' | 'duplicate' | 'error'; message: string } | null>(null);
  const ingestInputRef = useRef<HTMLInputElement>(null);

  const { data: stats } = useQuery<GalleryStats>({
    queryKey: ['retrieval-stats'],
    queryFn: () => api.get('/intelligence/retrieval/stats').then((r) => r.data),
    retry: 1,
  });

  useEffect(() => {
    return () => { if (queryPreview) URL.revokeObjectURL(queryPreview); };
  }, [queryPreview]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setResult(null);
    setError('');
    setExpandedCorrespondence(null);
    if (selected) {
      const url = URL.createObjectURL(selected);
      setQueryPreview(url);
    } else {
      setQueryPreview(null);
    }
  }

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError('');
    setResult(null);
    setExpandedCorrespondence(null);
    const body = new FormData();
    body.append('file', file);
    body.append('k', String(kCount));
    try {
      const response = await api.post<Result>('/intelligence/retrieval/search', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 240000,
      });
      setResult(response.data);
      queryClient.invalidateQueries({ queryKey: ['retrieval-stats'] });
    } catch {
      setError('Search could not complete. Check that the ML service, pretrained weights and photograph gallery are available.');
    } finally {
      setBusy(false);
    }
  }

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!ingestFile) return;
    setIngestBusy(true);
    setIngestStatus(null);
    const body = new FormData();
    body.append('file', ingestFile);
    try {
      const res = await api.post('/intelligence/retrieval/gallery/add', body, {
        timeout: 240000,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.added) {
        setIngestStatus({
          type: 'success',
          message: `Added image to gallery. Total records: ${res.data.gallery_size}.`,
        });
        setIngestFile(null);
        if (ingestInputRef.current) ingestInputRef.current.value = '';
        queryClient.invalidateQueries({ queryKey: ['retrieval-stats'] });
      } else {
        setIngestStatus({
          type: 'duplicate',
          message: 'Photograph already exists in gallery (exact duplicate SHA-256).',
        });
      }
    } catch {
      setIngestStatus({
        type: 'error',
        message: 'Could not add image. Ensure the ML service is running and image is valid JPEG/PNG.',
      });
    } finally {
      setIngestBusy(false);
    }
  }

  return (
    <main className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Historical Photograph Retrieval</h1>
          <p className="mt-1 text-sm text-slate-500">
            Find visually related evidence for investigator review. Similarity does not establish fraud or damage identity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {stats && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-600 shadow-sm">
              <Database className="w-3.5 h-3.5 text-primary-600" />
              <span>{stats.gallery_size} gallery images</span>
              <span className="text-slate-300">·</span>
              <span className="font-mono text-[11px]">{stats.embedding ?? 'Model loads on first use'}</span>
            </div>
          )}
          <button
            onClick={() => setShowAddModal((v) => !v)}
            className="btn-secondary text-xs flex items-center gap-1.5 py-1.5"
          >
            <PlusCircle className="w-3.5 h-3.5 text-primary-600" />
            {showAddModal ? 'Close Ingest' : 'Ingest Image'}
          </button>
        </div>
      </header>

      {/* Ingest Panel */}
      {showAddModal && (
        <div className="card p-5 border-primary-200 bg-primary-50/20 space-y-3">
          <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Database className="w-4 h-4 text-primary-600" />
            Dynamic Gallery Ingestion
          </h2>
          <p className="text-xs text-slate-600">
            Upload new historical photographs directly into the active retrieval index. Images will be embedded and available immediately for similarity ranking.
          </p>
          <form onSubmit={handleIngest} className="flex flex-wrap items-center gap-3">
            <input
              ref={ingestInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={ingestBusy}
              onChange={(e) => {
                setIngestFile(e.target.files?.[0] || null);
                setIngestStatus(null);
              }}
              className="text-xs text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 cursor-pointer"
            />
            <button
              type="submit"
              disabled={!ingestFile || ingestBusy}
              className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 disabled:opacity-50"
            >
              {ingestBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              {ingestBusy ? 'Indexing…' : 'Add to Index'}
            </button>
          </form>
          {ingestStatus && (
            <div
              className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                ingestStatus.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : ingestStatus.type === 'duplicate'
                  ? 'bg-amber-50 text-amber-800 border border-amber-200'
                  : 'bg-red-50 text-red-800 border border-red-200'
              }`}
            >
              {ingestStatus.type === 'success' && <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />}
              {ingestStatus.type === 'duplicate' && <Info className="w-4 h-4 text-amber-600 flex-shrink-0" />}
              {ingestStatus.type === 'error' && <Info className="w-4 h-4 text-red-600 flex-shrink-0" />}
              <span>{ingestStatus.message}</span>
            </div>
          )}
        </div>
      )}

      {/* Upload Section */}
      <div className="card p-6">
        <form onSubmit={search} className="space-y-4">
          <div className="flex items-start gap-6">
            {/* Upload area */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-2" htmlFor="query-photo">
                Query photograph
              </label>
              <div
                className="relative border-2 border-dashed border-slate-200 rounded-xl p-6 text-center hover:border-primary-300 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  id="query-photo"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={busy}
                  onChange={handleFileChange}
                  className="hidden"
                />
                <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <p className="text-sm text-slate-600">
                  {file ? file.name : 'Click to select a photograph'}
                </p>
                <p className="text-xs text-slate-400 mt-1">JPEG, PNG or WebP · up to 4 MB on hosted deployments</p>
              </div>
            </div>

            {/* Query preview */}
            {queryPreview && (
              <div className="w-48 flex-shrink-0">
                <p className="text-sm font-medium text-slate-700 mb-2">Preview</p>
                <img
                  src={queryPreview}
                  alt="Query preview"
                  className="w-full h-36 object-contain bg-slate-100 rounded-lg border border-slate-200"
                />
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={!file || busy}
                className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Search className="w-4 h-4" />
                {busy ? 'Searching photographs…' : 'Find historical candidates'}
              </button>
              {busy && (
                <p className="text-sm text-slate-500 animate-pulse flex items-center gap-1.5">
                  <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                  Initial model loading can take a minute…
                </p>
              )}
            </div>

            {/* Candidate count selection */}
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <label htmlFor="k-select" className="font-medium">
                Top results:
              </label>
              <select
                id="k-select"
                value={kCount}
                onChange={(e) => setKCount(Number(e.target.value))}
                disabled={busy}
                className="bg-white border border-slate-200 rounded px-2.5 py-1 text-xs focus:ring-1 focus:ring-primary-500 outline-none"
              >
                <option value={3}>3 candidates</option>
                <option value={5}>5 candidates</option>
                <option value={10}>10 candidates</option>
              </select>
            </div>
          </div>
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <Info className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <section aria-live="polite" className="space-y-4">
          {/* Summary bar */}
          <div className="flex items-center gap-4 px-1">
            <span className="badge bg-blue-50 text-blue-700">
              <Layers className="w-3 h-3 mr-1" />
              {result.gallery_size} gallery images
            </span>
            <span className="badge bg-slate-100 text-slate-600">{result.embedding}</span>
            <span className="badge bg-amber-50 text-amber-700">
              Investigator review required
            </span>
          </div>

          {result.candidates.length === 0 ? (
            <div className="card p-10 text-center text-slate-400">
              <Eye className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>The gallery contains no photographs.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {result.candidates.map((candidate, index) => {
                const hasCorrespondences = (candidate.verification.correspondences?.length ?? 0) > 0
                  && candidate.verification.query_size?.every(n => n > 0)
                  && candidate.verification.candidate_size?.every(n => n > 0);
                const isExpanded = expandedCorrespondence === index;

                return (
                  <article key={candidate.image_id} className="card overflow-hidden">
                    <div className="flex flex-col md:flex-row">
                      {/* Candidate thumbnail */}
                      <div className="md:w-72 flex-shrink-0 bg-slate-100">
                        <img
                          src={candidate.thumbnail}
                          alt={`Historical candidate ${index + 1}`}
                          className="w-full h-56 object-contain"
                        />
                      </div>

                      {/* Details */}
                      <div className="flex-1 p-5 space-y-3">
                        <div className="flex items-start justify-between">
                          <div>
                            <h2 className="font-semibold text-slate-900">
                              #{index + 1} — {candidate.image_id}
                            </h2>
                            <p className="text-xs text-slate-400 mt-0.5">
                              {candidate.verification.method.replace(/_/g, ' ')}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-2xl font-bold text-slate-900">
                              {candidate.cosine_similarity.toFixed(3)}
                            </p>
                            <p className="text-xs text-slate-400">cosine similarity</p>
                          </div>
                        </div>

                        {/* Metrics row */}
                        <div className="flex flex-wrap gap-3">
                          <div className="bg-slate-50 rounded-lg px-3 py-2">
                            <p className="text-xs text-slate-500">Correspondences</p>
                            <p className="text-sm font-semibold">{candidate.verification.matches}</p>
                          </div>
                          {candidate.verification.inliers !== undefined && (
                            <div className="bg-slate-50 rounded-lg px-3 py-2">
                              <p className="text-xs text-slate-500">RANSAC inliers</p>
                              <p className="text-sm font-semibold">{candidate.verification.inliers}</p>
                            </div>
                          )}
                          {candidate.damage_evidence?.available && (
                            <>
                              <div className="bg-emerald-50 rounded-lg px-3 py-2">
                                <p className="text-xs text-emerald-600">In damage region</p>
                                <p className="text-sm font-semibold text-emerald-700">
                                  {candidate.damage_evidence.damage_supported_correspondences} / {candidate.damage_evidence.evaluated_correspondences}
                                </p>
                              </div>
                              <div className="bg-orange-50 rounded-lg px-3 py-2">
                                <p className="text-xs text-orange-600">Damage mask Δ</p>
                                <p className="text-sm font-semibold text-orange-700">
                                  {candidate.damage_evidence.damage_mask_score_drop?.toFixed(3) ?? '—'}
                                </p>
                              </div>
                              <div className="bg-slate-50 rounded-lg px-3 py-2">
                                <p className="text-xs text-slate-500">Background Δ</p>
                                <p className="text-sm font-semibold">
                                  {candidate.damage_evidence.background_mask_score_drop?.toFixed(3) ?? 'No control'}
                                </p>
                              </div>
                            </>
                          )}
                          {candidate.damage_evidence && !candidate.damage_evidence.available && (
                            <div className="bg-slate-50 rounded-lg px-3 py-2">
                              <p className="text-xs text-slate-500">Damage evidence</p>
                              <p className="text-sm text-slate-400 italic">
                                {candidate.damage_evidence.reason?.replace(/_/g, ' ')}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* Correspondence toggle */}
                        {hasCorrespondences && queryPreview && (
                          <button
                            onClick={() => setExpandedCorrespondence(isExpanded ? null : index)}
                            className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1.5 transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                            {isExpanded ? 'Hide correspondence lines' : 'Show correspondence lines'}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expanded correspondence overlay */}
                    {isExpanded && hasCorrespondences && queryPreview && (
                      <div className="border-t border-slate-200 p-5 bg-slate-50/50">
                        <CorrespondenceOverlay
                          queryImage={queryPreview}
                          candidateImage={candidate.thumbnail}
                          correspondences={candidate.verification.correspondences!}
                          querySize={candidate.verification.query_size!}
                          candidateSize={candidate.verification.candidate_size!}
                          method={candidate.verification.method.replace(/_/g, ' ')}
                        />
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}

          {/* Disclaimer */}
          <p className="text-xs text-slate-400 px-1">
            Masking measures model sensitivity to an artificial perturbation; it does not prove identity.
            Large similarity values are not probabilities. A person must review the candidates.
          </p>
        </section>
      )}
    </main>
  );
}
