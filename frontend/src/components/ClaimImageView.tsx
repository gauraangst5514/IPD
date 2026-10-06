import { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuthStore } from "../store/auth";
import ImageCompareSlider from "./ImageCompareSlider";

function usePrivateImage(path: string | null) {
  const token = useAuthStore((state) => state.token);
  const [source, setSource] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setSource(null);
    setFailed(false);
    if (path && token) {
      api.get(path.replace(/^\/api\/v1/, ""), { responseType: "blob", signal: controller.signal })
        .then(({ data }) => {
          if (controller.signal.aborted) return;
          objectUrl = URL.createObjectURL(data);
          setSource(objectUrl);
        })
        .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    }
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path, token]);
  return { source, failed };
}

export default function ClaimImageView({ original, annotated }: { original: string; annotated: string | null }) {
  const originalImage = usePrivateImage(original);
  const annotatedImage = usePrivateImage(annotated);
  if (originalImage.failed) return <p className="p-4 text-red-700" role="alert">Photo could not be loaded. Refresh to retry.</p>;
  if (!originalImage.source) return <p className="p-4 text-slate-500">Loading photo…</p>;
  return (
    <div>
      {annotatedImage.source ? (
        <ImageCompareSlider originalSrc={originalImage.source} annotatedSrc={annotatedImage.source} />
      ) : <img src={originalImage.source} alt="Uploaded damage photo" className="w-full max-h-[500px] object-contain" />}
      {annotatedImage.failed && <p className="p-3 text-sm text-amber-700">Annotated preview unavailable.</p>}
    </div>
  );
}
