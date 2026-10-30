import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Database, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../lib/api';

interface Props {
  claimImageId: string;
}

export default function AddToGalleryButton({ claimImageId }: Props) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{
    type: 'success' | 'duplicate' | 'error';
    message: string;
  } | null>(null);

  async function handleIndex() {
    setLoading(true);
    setStatus(null);
    try {
      const formData = new FormData();
      formData.append('claim_image_id', claimImageId);
      const res = await api.post('/intelligence/retrieval/gallery/add', formData, {
        timeout: 240000,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      queryClient.invalidateQueries({ queryKey: ['retrieval-stats'] });
      if (res.data.added) {
        setStatus({
          type: 'success',
          message: `Indexed in gallery (${res.data.gallery_size} total)`,
        });
      } else {
        setStatus({
          type: 'duplicate',
          message: 'Already exists in gallery',
        });
      }
    } catch {
      setStatus({
        type: 'error',
        message: 'Failed to index image in retrieval gallery',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      {status ? (
        <span
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-medium ${
            status.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : status.type === 'duplicate'
              ? 'bg-slate-100 text-slate-700 border border-slate-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {status.type === 'success' && <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />}
          {status.type === 'duplicate' && <Database className="w-3.5 h-3.5 text-slate-500" />}
          {status.type === 'error' && <AlertCircle className="w-3.5 h-3.5 text-red-500" />}
          {status.message}
        </span>
      ) : null}
      {(!status || status.type === 'error') && (
        <button
          onClick={handleIndex}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors disabled:opacity-50"
          title="Add this photograph to the historical retrieval gallery for cross-claim similarity searches"
        >
          {loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary-600" />
          ) : (
            <Database className="w-3.5 h-3.5 text-slate-500" />
          )}
          {loading ? 'Indexing…' : 'Index in retrieval gallery'}
        </button>
      )}
    </div>
  );
}
