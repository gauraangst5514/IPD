"""Detection-target occlusion sensitivity for the actual active damage detector."""
import io
import numpy as np
from PIL import Image

def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    area = max(0, min(ax+aw/2,bx+bw/2)-max(ax-aw/2,bx-bw/2)) * max(0,min(ay+ah/2,by+bh/2)-max(ay-ah/2,by-bh/2))
    return area / max(aw*ah+bw*bh-area, 1e-9)

def occlusion_saliency(detector, image_bytes, grid=4):
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Bound CPU work and output size; same image is used for baseline and occlusions.
    original.thumbnail((800,800))
    stream = io.BytesIO()
    original.save(stream, format="PNG")
    result = detector.detect(stream.getvalue())
    if not result.get("damage_analysis_available") or not result["detections"]:
        return None
    target = max(result["detections"], key=lambda d:d["confidence"])
    pixels = np.array(original)
    height, width = pixels.shape[:2]
    heatmap = np.zeros((grid,grid), dtype=np.float32)
    for row in range(grid):
        for col in range(grid):
            masked = pixels.copy()
            y1,y2 = row*height//grid, (row+1)*height//grid
            x1,x2 = col*width//grid, (col+1)*width//grid
            masked[y1:y2,x1:x2] = np.mean(pixels, axis=(0,1)).astype(np.uint8)
            stream = io.BytesIO()
            Image.fromarray(masked).save(stream, format="PNG")
            detections = detector.detect(stream.getvalue())["detections"]
            confidence = max((d["confidence"] for d in detections
                              if d["label"] == target["label"] and overlap(d["bbox"],target["bbox"]) >= .2), default=0)
            heatmap[row,col] = max(0, target["confidence"]-confidence)
    # Keep absolute score drops, rather than normalize tiny noise to a full heatmap.
    overlay = np.array(Image.fromarray((np.clip(heatmap,0,1)*255).astype(np.uint8)).resize(original.size, Image.Resampling.NEAREST))/255.
    red = np.zeros_like(pixels); red[:,:,0] = 255
    alpha = overlay[:,:,None]*.75
    output = Image.fromarray((pixels*(1-alpha)+red*alpha).astype(np.uint8))
    stream = io.BytesIO(); output.save(stream,format="PNG")
    return {"image": stream.getvalue(), "target":target, "score_drops":heatmap.tolist(),
            "method":"occlusion_sensitivity", "grid":grid,
            "warning":"Sensitivity to grey masking of a selected detection; not proof of damage cause, tampering or fraud."}
