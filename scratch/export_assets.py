import re
import shutil
from pathlib import Path

html_content = Path("tendertrust_architecture.html").read_text(encoding="utf-8")

# Extract the SVG element
match = re.search(r'(<svg\b[^>]*\bviewBox="0 0 1200 675"[^>]*>.*?</svg>)', html_content, re.DOTALL)
if not match:
    match = re.search(r'(<svg\b[^>]*>.*?</svg>)', html_content, re.DOTALL)

if match:
    svg_code = match.group(1)
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    
    # Extract stylesheet or embed styles if needed for standalone SVG viewing
    style_match = re.search(r'(<style\b[^>]*>.*?</style>)', html_content, re.DOTALL)
    if style_match:
        style_block = style_match.group(1)
        # Inject style into svg defs
        svg_code = svg_code.replace("</svg>", f"<defs>{style_block}</defs></svg>")
        
    Path("tendertrust_architecture.svg").write_text(svg_code, encoding="utf-8")
    print(f"Exported tendertrust_architecture.svg ({len(svg_code)} bytes)")
else:
    print("Could not find SVG in HTML")

# Copy the high-res PNG
src_png = Path("tendertrust_architecture.visual-check.2048x1320.light.png")
if src_png.exists():
    shutil.copy2(src_png, Path("tendertrust_architecture.png"))
    print(f"Exported tendertrust_architecture.png from {src_png.name}")
else:
    print(f"Source PNG {src_png} not found")
