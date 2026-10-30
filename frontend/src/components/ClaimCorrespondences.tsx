import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import CorrespondenceOverlay from './CorrespondenceOverlay';

type Candidate = {
  image_id: string;
  thumbnail: string;
  verification: {
    method: string;
    correspondences?: { query: [number, number]; candidate: [number, number] }[];
    query_size?: [number, number];
    candidate_size?: [number, number];
  };
};

export default function ClaimCorrespondences({ imageId, originalUrl }: { imageId: string; originalUrl: string }) {
  const [open, setOpen] = useState(() => new URLSearchParams(window.location.search).get('correspondences') === '1');
  const [selection, setSelection] = useState(0);
  const { data, isFetching, isError, refetch } = useQuery({
    queryKey: ['claim-correspondences', imageId],
    enabled: open,
    staleTime: 60000,
    retry: false,
    queryFn: async ({ signal }) => {
      const photo = await fetch(originalUrl, { signal });
      if (!photo.ok) throw new Error('Photograph could not be loaded');
      const body = new FormData();
      body.append('file', await photo.blob(), 'claim-query.jpg');
      body.append('k', '5');
      const response = await api.post<{ candidates: Candidate[] }>('/intelligence/retrieval/search', body, {
        headers: { 'Content-Type': 'multipart/form-data' }, timeout: 240000, signal,
      });
      return response.data;
    },
  });
  const candidates = data?.candidates ?? [];
  const candidate = candidates[selection];
  const verification = candidate?.verification;
  const hasGeometry = verification?.query_size?.every(n => n > 0)
    && verification.candidate_size?.every(n => n > 0)
    && Boolean(verification.correspondences?.length);
  return <section className="border-t p-4 space-y-3" aria-label="Photograph correspondence viewer">
    <button type="button" className="btn-secondary text-sm" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {open ? 'Hide correspondence viewer' : 'Show matching dots and lines'}
    </button>
    {open && <div className="space-y-3" aria-live="polite">
      <h3 className="font-semibold">Matching dots and lines</h3>
      <p className="text-xs text-slate-500">Dots mark matched visual features; lines connect them across photographs. A deliberately indexed copy demonstrates a same-image match. Matches alone do not establish recurring damage or fraud.</p>
      {isFetching && <p role="status" className="text-sm">Finding candidates and geometric correspondences…</p>}
      {isError && <div role="alert" className="text-sm text-red-700">Correspondence search could not complete. <button type="button" className="underline" onClick={() => void refetch()}>Retry</button></div>}
      {candidates.length > 0 && <label className="block text-sm">Compare with gallery photograph
        <select className="block w-full border rounded p-2 mt-1" value={selection} onChange={event => setSelection(Number(event.target.value))}>
          {candidates.map((item, index) => <option key={item.image_id} value={index}>{index + 1}. {item.image_id} · {item.verification.correspondences?.length ?? 0} correspondences</option>)}
        </select>
      </label>}
      {candidate && verification && (hasGeometry ? <CorrespondenceOverlay
        key={candidate.image_id} queryImage={originalUrl} candidateImage={candidate.thumbnail}
        correspondences={verification.correspondences!} querySize={verification.query_size!}
        candidateSize={verification.candidate_size!} method={verification.method}
      /> : <p className="text-sm text-slate-500">No geometric correspondences for this candidate. Select another photograph.</p>)}
      {data && !isFetching && !candidates.length && <p className="text-sm">No indexed photographs are available.</p>}
    </div>}
  </section>;
}
