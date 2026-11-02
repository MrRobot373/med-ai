"""Contact sheet of a captured shot: evenly spaced frames with their film times."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw

shot = Path(__file__).parent / "out" / sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
out = sys.argv[3]
d = json.loads((shot / "shot.json").read_text())
frames = d["frames"]
pick = [frames[round(i * (len(frames) - 1) / max(1, n - 1))] for i in range(n)] if len(frames) > n else frames
w, h = 800, 450
cols = 2
rows = (len(pick) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), "white")
for i, f in enumerate(pick):
    im = Image.open(shot / f["file"]).convert("RGB").resize((w, h))
    ImageDraw.Draw(im).text((8, 8), f"t={f['t']}", fill="red")
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out, quality=85)
