"""PRUBETH Sovereign Beach Theme Logo Generator.
Creates vector SVG and HTML showcase for PRUBETH full logo inspired by Mistral AI modular block grid.
"""

import os
from pathlib import Path

def generate_prubeth_beach_svg() -> str:
    # 7x7 modular letter definitions (width=5, height=7)
    letters = {
        'P': [
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 0],
            [1, 0, 0, 0, 0],
            [1, 0, 0, 0, 0],
        ],
        'R': [
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 0],
            [1, 0, 1, 0, 0],
            [1, 0, 0, 1, 0],
            [1, 0, 0, 0, 1],
        ],
        'U': [
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [0, 1, 1, 1, 0],
        ],
        'B': [
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 0],
        ],
        'E': [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0],
            [1, 0, 0, 0, 0],
            [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 0],
            [1, 0, 0, 0, 0],
            [1, 1, 1, 1, 1],
        ],
        'T': [
            [1, 1, 1, 1, 1],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
        ],
        'H': [
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
        ]
    }

    # Beach Theme Spectrum (Vertical sunset coral -> golden sand -> turquoise seafoam -> ocean azure)
    row_colors = [
        "#FF3366",  # Row 0: Sunset Hibiscus / Coral Pink
        "#FF6B35",  # Row 1: Tropical Sunset Tangerine
        "#F7B801",  # Row 2: Radiant Golden Hour Sunlight
        "#E8CA65",  # Row 3: Warm Sand Dunes Amber
        "#00F5D4",  # Row 4: Sparkling Lagoon Seafoam
        "#00BBF9",  # Row 5: Caribbean Turquoise Surf
        "#0077B6"   # Row 6: Deep Royal Oceanic Blue
    ]

    # Sovereign P Crest (Mistral Stepped Block Geometry on 9x9 grid)
    # 0 = empty, 1 = tile
    emblem_grid = [
        # y=0: Sunset Coral Horizon (stepped chevron crest)
        [0, 0, 1, 1, 1, 1, 1, 0, 0],
        # y=1: Sunset Tangerine
        [0, 1, 1, 0, 0, 0, 1, 1, 0],
        # y=2: Golden Sand Peak
        [0, 1, 1, 0, 0, 0, 0, 1, 1],
        # y=3: Golden Sand Body
        [0, 1, 1, 0, 0, 0, 0, 1, 1],
        # y=4: Turquoise Seafoam Loop Bridge
        [0, 1, 1, 1, 1, 1, 1, 1, 0],
        # y=5: Caribbean Lagoon Pillar
        [0, 1, 1, 0, 0, 0, 0, 0, 0],
        # y=6: Azure Ocean Reef
        [0, 1, 1, 0, 0, 0, 0, 0, 0],
        # y=7: Deep Ocean Base Pedestal
        [1, 1, 1, 1, 0, 0, 0, 0, 0],
        # y=8: Oceanic Foundation
        [1, 1, 1, 1, 0, 0, 0, 0, 0],
    ]

    emblem_colors = [
        "#FF2A55",  # 0: Coral Sunset
        "#FF6230",  # 1: Tropic Orange
        "#FF9F1C",  # 2: Golden Sand
        "#FFBF00",  # 3: Bright Sunlight
        "#05F1CD",  # 4: Tropical Surf
        "#00C4FF",  # 5: Turquoise Blue
        "#0088E8",  # 6: Deep Marine
        "#0055B3",  # 7: Abyssal Blue
        "#003080",  # 8: Sovereign Anchor
    ]

    emblem_tile_size = 20
    emblem_gap = 4
    emblem_pitch = emblem_tile_size + emblem_gap
    emblem_width = 9 * emblem_pitch
    emblem_start_x = (1200 - emblem_width) / 2
    emblem_start_y = 65

    emblem_svg_elements = []
    for r_idx, r in enumerate(emblem_grid):
        color = emblem_colors[r_idx]
        for c_idx, val in enumerate(r):
            if val:
                x = emblem_start_x + c_idx * emblem_pitch
                y = emblem_start_y + r_idx * emblem_pitch
                emblem_svg_elements.append(
                    f'      <rect x="{x}" y="{y}" width="{emblem_tile_size}" height="{emblem_tile_size}" rx="3.5" fill="{color}" filter="url(#tileGlow)" />'
                )

    # Wordmark letters assembly
    tile_size = 13
    gap = 3.5
    pitch = tile_size + gap
    letter_width_px = 5 * pitch
    letter_spacing_px = 2.4 * pitch
    
    total_wordmark_width = (7 * letter_width_px) + (6 * letter_spacing_px)
    wordmark_start_x = (1200 - total_wordmark_width) / 2
    wordmark_start_y = 330

    wordmark_svg_elements = []
    current_x = wordmark_start_x
    for char in ['P', 'R', 'U', 'B', 'E', 'T', 'H']:
        char_grid = letters[char]
        for r_idx, row in enumerate(char_grid):
            color = row_colors[r_idx]
            for c_idx, val in enumerate(row):
                if val:
                    x = current_x + c_idx * pitch
                    y = wordmark_start_y + r_idx * pitch
                    wordmark_svg_elements.append(
                        f'      <rect x="{x:.1f}" y="{y:.1f}" width="{tile_size}" height="{tile_size}" rx="2.5" fill="{color}" />'
                    )
        current_x += letter_width_px + letter_spacing_px

    emblem_str = "\n".join(emblem_svg_elements)
    wordmark_str = "\n".join(wordmark_svg_elements)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 520" width="1200" height="520">
  <defs>
    <!-- Background: Midnight Ocean Slate with Tropical Horizon -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#080E18" />
      <stop offset="45%" stop-color="#0D1826" />
      <stop offset="100%" stop-color="#050B12" />
    </linearGradient>

    <!-- Warm Golden Sand Sun Glow Filter -->
    <filter id="ambientSun" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="60" />
    </filter>

    <!-- Ocean Wave Mist Glow -->
    <filter id="oceanMist" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="50" />
    </filter>

    <!-- Subtle Pixel Block Glow -->
    <filter id="tileGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.5" />
    </filter>

    <!-- Beach Horizon Wave Divider -->
    <linearGradient id="waveLine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FF3366" stop-opacity="0" />
      <stop offset="25%" stop-color="#FF9F1C" stop-opacity="0.8" />
      <stop offset="50%" stop-color="#00F5D4" stop-opacity="1" />
      <stop offset="75%" stop-color="#00BBF9" stop-opacity="0.8" />
      <stop offset="100%" stop-color="#0077B6" stop-opacity="0" />
    </linearGradient>
  </defs>

  <!-- Deep Night Ocean Canvas -->
  <rect width="1200" height="520" fill="url(#bgGrad)" />

  <!-- Atmospheric Beach Lighting: Sun Warmth & Turquoise Surf Reflections -->
  <circle cx="600" cy="160" r="180" fill="#FF8500" opacity="0.10" filter="url(#ambientSun)" />
  <circle cx="600" cy="380" r="240" fill="#00F5D4" opacity="0.08" filter="url(#oceanMist)" />

  <!-- Horizon Wave Divider Line -->
  <line x1="280" y1="298" x2="920" y2="298" stroke="url(#waveLine)" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.4" />

  <!-- ==================== PRUBETH SOVEREIGN EMBLEM (MISTRAL-INSPIRED STEPPED GRID) ==================== -->
  <g id="prubeth-crest">
{emblem_str}
  </g>

  <!-- ==================== PRUBETH MODULAR PIXEL WORDMARK ==================== -->
  <g id="prubeth-wordmark">
{wordmark_str}
  </g>

  <!-- Sovereign Edition Sub-text -->
  <g id="prubeth-subline" transform="translate(600, 475)">
    <text text-anchor="middle" font-family="'JetBrains Mono', 'SF Mono', Consolas, monospace" font-size="12" font-weight="700" letter-spacing="8" fill="#48CAE4" opacity="0.75">
      SOVEREIGN DEVELOPER EDITION
    </text>
  </g>
</svg>"""
    return svg

def main():
    svg_code = generate_prubeth_beach_svg()
    
    # 1. Save in local assets/
    assets_dir = Path("assets")
    assets_dir.mkdir(exist_ok=True)
    svg_path = assets_dir / "prubeth_beach_logo.svg"
    svg_path.write_text(svg_code, encoding="utf-8")
    print(f"Generated SVG: {svg_path.resolve()}")

    # 2. Save in conversation artifact directory
    artifact_dir = Path(r"C:\Users\asus\.gemini\antigravity\brain\bb91c880-6116-4761-9938-8870c1183574")
    artifact_svg_path = artifact_dir / "prubeth_beach_logo.svg"
    artifact_svg_path.write_text(svg_code, encoding="utf-8")
    print(f"Generated Artifact SVG: {artifact_svg_path.resolve()}")

    # 3. Save Interactive HTML Showcase
    html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PRUBETH — Beach Theme Sovereign Logo</title>
  <style>
    body {{
      margin: 0;
      background: #060A10;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      color: #ECEFF4;
    }}
    .container {{
      max-width: 1200px;
      padding: 40px;
      text-align: center;
    }}
    .card {{
      background: rgba(13, 24, 38, 0.7);
      border: 1px solid rgba(0, 245, 212, 0.2);
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7), 0 0 40px rgba(0, 245, 212, 0.1);
      padding: 30px;
      margin-bottom: 24px;
      backdrop-filter: blur(12px);
    }}
    h1 {{
      font-size: 24px;
      letter-spacing: 4px;
      margin-top: 10px;
      color: #00F5D4;
      text-transform: uppercase;
    }}
    p {{
      color: #8892B0;
      font-size: 14px;
      line-height: 1.6;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      background: linear-gradient(90deg, #FF3366, #FF9F1C, #00F5D4);
      color: #050B14;
      margin-bottom: 12px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="badge">PRUBETH SOVEREIGN EDITION</div>
    <div class="card">
      {svg_code}
    </div>
    <p>Inspired by Mistral AI's modular pixel block geometry · Beach Theme Palette (Sunset Coral → Golden Sand → Turquoise Seafoam → Ocean Azure)</p>
  </div>
</body>
</html>"""
    html_path = artifact_dir / "prubeth_beach_logo_showcase.html"
    html_path.write_text(html_code, encoding="utf-8")
    print(f"Generated HTML Showcase: {html_path.resolve()}")

if __name__ == "__main__":
    main()
