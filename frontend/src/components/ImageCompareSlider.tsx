import { useState, useRef, useCallback } from "react";

interface ImageCompareSliderProps {
  originalSrc: string;
  annotatedSrc: string;
  originalLabel?: string;
  annotatedLabel?: string;
}

/**
 * Before/After image comparison slider.
 * Drag the handle to reveal the AI-annotated detection overlay.
 */
export default function ImageCompareSlider({
  originalSrc,
  annotatedSrc,
  originalLabel = "Original",
  annotatedLabel = "AI Detection",
}: ImageCompareSliderProps) {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const handleMove = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const pct = Math.max(2, Math.min(98, (x / rect.width) * 100));
    setSliderPos(pct);
  }, []);

  const onMouseDown = () => { dragging.current = true; };
  const onMouseUp = () => { dragging.current = false; };
  const onMouseMove = (e: React.MouseEvent) => {
    if (dragging.current) handleMove(e.clientX);
  };
  const onTouchMove = (e: React.TouchEvent) => {
    handleMove(e.touches[0].clientX);
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-hidden rounded-lg cursor-col-resize select-none bg-slate-100"
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onTouchMove={onTouchMove}
      onTouchEnd={onMouseUp}
    >
      {/* Annotated image (full background) */}
      <img
        src={annotatedSrc}
        alt={annotatedLabel}
        className="block w-full h-auto"
        draggable={false}
      />

      {/* Original image (clipped overlay) */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ clipPath: `inset(0 ${100 - sliderPos}% 0 0)` }}
      >
        <img
          src={originalSrc}
          alt={originalLabel}
          className="block w-full h-full object-cover"
          draggable={false}
        />
      </div>

      {/* Slider line + handle */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-white/90 z-10"
        style={{ left: `${sliderPos}%`, transform: "translateX(-50%)" }}
      >
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center cursor-col-resize border-2 border-primary-500"
          onMouseDown={onMouseDown}
          onTouchStart={onMouseDown}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-primary-600">
            <path d="M5 3L2 8L5 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M11 3L14 8L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 px-2.5 py-1 bg-black/60 text-white text-[11px] rounded font-medium backdrop-blur-sm z-10">
        {originalLabel}
      </div>
      <div className="absolute top-3 right-3 px-2.5 py-1 bg-black/60 text-white text-[11px] rounded font-medium backdrop-blur-sm z-10">
        {annotatedLabel}
      </div>
    </div>
  );
}
