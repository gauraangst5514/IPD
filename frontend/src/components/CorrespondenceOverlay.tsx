import { useCallback, useEffect, useRef, useState } from 'react';

interface Correspondence {
  query: [number, number];
  candidate: [number, number];
}

interface Props {
  queryImage: string;
  candidateImage: string;
  correspondences: Correspondence[];
  querySize: [number, number];      // [width, height] of the image used for matching
  candidateSize: [number, number];  // [width, height] of the image used for matching
  method: string;
}

const LINE_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
];

/**
 * Side-by-side query + candidate with SVG correspondence lines.
 * Coordinates from the engine refer to resized match images;
 * we scale them to the displayed image dimensions.
 */
export default function CorrespondenceOverlay({
  queryImage, candidateImage, correspondences,
  querySize, candidateSize, method,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const queryImgRef = useRef<HTMLImageElement>(null);
  const candidateImgRef = useRef<HTMLImageElement>(null);
  const [dims, setDims] = useState<{
    qw: number; qh: number; cw: number; ch: number;
    qOffX: number; qOffY: number; cOffX: number; cOffY: number;
    totalW: number; totalH: number; gap: number;
  } | null>(null);
  const [showLines, setShowLines] = useState(true);
  const [loaded, setLoaded] = useState({ query: false, candidate: false });

  const measure = useCallback(() => {
    const container = containerRef.current;
    const qImg = queryImgRef.current;
    const cImg = candidateImgRef.current;
    if (!container || !qImg || !cImg) return;
    if (!qImg.naturalWidth || !cImg.naturalWidth) return;

    const containerRect = container.getBoundingClientRect();
    const qRect = qImg.getBoundingClientRect();
    const cRect = cImg.getBoundingClientRect();

    setDims({
      qw: qRect.width, qh: qRect.height,
      cw: cRect.width, ch: cRect.height,
      qOffX: qRect.left - containerRect.left,
      qOffY: qRect.top - containerRect.top,
      cOffX: cRect.left - containerRect.left,
      cOffY: cRect.top - containerRect.top,
      totalW: containerRect.width,
      totalH: containerRect.height,
      gap: 12,
    });
  }, []);

  useEffect(() => {
    if (loaded.query && loaded.candidate) {
      // Small delay so the browser finishes layout
      const timer = setTimeout(measure, 50);
      return () => clearTimeout(timer);
    }
  }, [loaded, measure]);

  useEffect(() => {
    const observer = new ResizeObserver(measure);
    for (const element of [containerRef.current, queryImgRef.current, candidateImgRef.current]) {
      if (element) observer.observe(element);
    }
    measure();
    return () => observer.disconnect();
  }, [measure, queryImage, candidateImage]);

  const lines = dims && showLines ? correspondences.map((c, i) => {
    // Scale from match-image coordinates to displayed coordinates
    const qx = dims.qOffX + (c.query[0] / querySize[0]) * dims.qw;
    const qy = dims.qOffY + (c.query[1] / querySize[1]) * dims.qh;
    const cx = dims.cOffX + (c.candidate[0] / candidateSize[0]) * dims.cw;
    const cy = dims.cOffY + (c.candidate[1] / candidateSize[1]) * dims.ch;
    return { x1: qx, y1: qy, x2: cx, y2: cy, color: LINE_COLORS[i % LINE_COLORS.length] };
  }) : [];

  if (correspondences.length === 0) {
    return (
      <p className="text-sm text-slate-500 italic">
        No geometric correspondences to visualize.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          <span className="font-medium">{correspondences.length}</span> correspondences · {method}
        </p>
        <button
          aria-pressed={showLines}
          onClick={() => setShowLines(v => !v)}
          className="text-xs px-2.5 py-1 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors"
        >
          {showLines ? 'Hide lines' : 'Show lines'}
        </button>
      </div>

      <div ref={containerRef} className="relative">
        <div className="flex gap-3 items-start">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-slate-500 mb-1 font-medium">Query</p>
            <img
              ref={queryImgRef}
              src={queryImage}
              alt="Query photograph"
              className="w-full h-auto rounded-lg border border-slate-200 bg-slate-100"
              onLoad={() => { setLoaded(prev => ({ ...prev, query: true })); measure(); }}
            />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-slate-500 mb-1 font-medium">Candidate</p>
            <img
              ref={candidateImgRef}
              src={candidateImage}
              alt="Candidate photograph"
              className="w-full h-auto rounded-lg border border-slate-200 bg-slate-100"
              onLoad={() => { setLoaded(prev => ({ ...prev, candidate: true })); measure(); }}
            />
          </div>
        </div>

        {/* SVG overlay for correspondence lines */}
        {dims && lines.length > 0 && (
          <svg
            className="absolute inset-0 pointer-events-none"
            width={dims.totalW}
            height={dims.totalH}
            style={{ zIndex: 10 }}
          >
            {/* Keypoint dots on query */}
            {lines.map((l, i) => (
              <circle key={`q${i}`} cx={l.x1} cy={l.y1} r={3}
                fill={l.color} opacity={0.9} stroke="white" strokeWidth={1} />
            ))}
            {/* Keypoint dots on candidate */}
            {lines.map((l, i) => (
              <circle key={`c${i}`} cx={l.x2} cy={l.y2} r={3}
                fill={l.color} opacity={0.9} stroke="white" strokeWidth={1} />
            ))}
            {/* Connecting lines */}
            {lines.map((l, i) => (
              <line key={`l${i}`}
                x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
                stroke={l.color} strokeWidth={1.2} opacity={0.55}
              />
            ))}
          </svg>
        )}
      </div>

      <p className="text-xs text-slate-400">
        Lines connect matching local features. Correspondences may include undamaged bodywork or background.
        They are geometric evidence, not proof of physical identity.
      </p>
    </div>
  );
}
