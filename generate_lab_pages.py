from PIL import Image, ImageDraw, ImageFont
import random
import math
import os

OUTPUT_DIR = "/Users/aziemer/physics_lab_demo/lab_pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_font(size):
    for path in [
        "/System/Library/Fonts/Noteworthy.ttc",
        "/System/Library/Fonts/MarkerFelt.ttc",
        "/Library/Fonts/Comic Sans MS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def jitter(x, y, amt=2):
    return x + random.randint(-amt, amt), y + random.randint(-amt, amt)

def draw_handwritten_text(draw, x, y, text, font, fill=(20, 20, 80)):
    jx, jy = jitter(x, y, 1)
    draw.text((jx, jy), text, font=font, fill=fill)

def add_paper_texture(img):
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for _ in range(800):
        rx, ry = random.randint(0, w), random.randint(0, h)
        c = random.randint(200, 240)
        draw.point((rx, ry), fill=(c, c, c - 10))
    for y_line in range(60, h, 28):
        draw.line([(40, y_line), (w - 40, y_line)], fill=(180, 200, 220), width=1)
    draw.line([(70, 30), (70, h - 30)], fill=(200, 140, 140), width=1)

def create_page(page_data, filename):
    img = Image.new('RGB', (800, 1100), (248, 245, 235))
    add_paper_texture(img)
    draw = ImageDraw.Draw(img)
    
    title_font = get_font(22)
    body_font = get_font(16)
    small_font = get_font(13)
    
    y = 40
    for line in page_data:
        if line.startswith("##"):
            draw_handwritten_text(draw, 80, y, line[2:].strip(), title_font, (20, 20, 100))
            y += 35
        elif line.startswith("---"):
            draw.line([(80, y), (720, y)], fill=(100, 100, 150), width=1)
            y += 15
        elif line.startswith("!"):
            draw_handwritten_text(draw, 80, y, line[1:].strip(), small_font, (150, 50, 50))
            y += 22
        elif line == "":
            y += 12
        else:
            draw_handwritten_text(draw, 80, y, line, body_font, (30, 30, 70))
            y += 24
    
    img.save(os.path.join(OUTPUT_DIR, filename), quality=92)

pages = [
    {
        "filename": "lab_notebook_page_001.jpg",
        "lines": [
            "## Experiment EXP-2024-002: Solid Ne Film Growth",
            "## Date: 5 Feb 2024   Researcher: M. Weber",
            "---",
            "Cryostat: BlueFors LD400",
            "Target T: 4.0 K    E_perp: 30 V/cm",
            "Film thickness target: 120 nm",
            "",
            "## Cooldown Log:",
            "09:15  Started precooling. LN2 trap active.",
            "10:30  T = 77K, switched to He4 cooling",
            "12:00  T = 20K, began Ne gas admission",
            "13:45  T = 8.2K, Ne film condensing",
            "14:30  T = 4.5K, film ~80nm (capacitance)",
            "15:15  T = 4.1K, film ~110nm",
            "16:00  T = 4.02K, film ~118nm STABLE",
            "",
            "## Conductivity Measurements (Sommer-Tanner):",
            "T(K)    sigma(S)      mu(cm2/Vs)",
            "4.02    7.8e-8        4.9e4",
            "4.05    7.6e-8        4.8e4",
            "4.10    7.3e-8        4.7e4",
            "4.15    7.1e-8        4.5e4",
            "4.25    6.8e-8        4.2e4",
            "4.50    6.2e-8        3.8e4",
            "5.00    5.5e-8        3.2e4",
            "",
            "!Note: Film looks stable. Good crystallinity.",
        ]
    },
    {
        "filename": "lab_notebook_page_002.jpg",
        "lines": [
            "## EXP-2024-003: H2 Substrate Mobility",
            "## 10 March 2024   A. Schmidt",
            "---",
            "Oxford Kelvinox dilution fridge",
            "Solid H2 film, thickness ~85nm",
            "Corbino electrode, AC method 100kHz",
            "",
            "## Temperature Sweep Data:",
            "T(K)    sigma(S)      n_e(cm-2)    mu(cm2/Vs)",
            "1.20    4.8e-8        3.1e7         2.1e4",
            "1.35    4.5e-8        3.2e7         1.9e4",
            "1.50    4.2e-8        3.0e7         1.8e4",
            "1.80    3.8e-8        3.1e7         1.6e4",
            "2.00    3.5e-8        3.3e7         1.4e4",
            "2.50    2.9e-8        3.2e7         1.1e4",
            "3.00    2.3e-8        3.0e7         0.9e4",
            "3.50    1.8e-8        3.1e7         0.7e4",
            "",
            "!Mobility decreasing with T as expected",
            "!(phonon scattering dominant above 2K)",
            "",
            "## Pressing Field Scan at T=1.5K:",
            "E(V/cm)   sigma(S)      mu",
            "20        3.9e-8        1.7e4",
            "30        4.1e-8        1.8e4",
            "40        4.2e-8        1.8e4",
            "50        4.0e-8        1.7e4",
            "60        3.7e-8        1.5e4",
            "!Optimal field ~ 35-45 V/cm",
        ]
    },
    {
        "filename": "lab_notebook_page_003.jpg",
        "lines": [
            "## EXP-2025-002: Ne Qubit T1 Measurement",
            "## 1 April 2025   Dr. M. Weber",
            "---",
            "BlueFors LD400, base T = 10 mK",
            "Ne film: 155nm, annealed 2 hrs at 12K",
            "E_perp = 30 V/cm",
            "",
            "## Rydberg transition frequencies:",
            "f_12 = 125.3 GHz  (ground -> 1st excited)",
            "f_23 = 42.1 GHz",
            "",
            "## Coherence measurements:",
            "Run#   T1(us)    T2*(us)    T2_echo(us)",
            "1      12.3      4.5        8.2",
            "2      13.1      4.8        8.7",
            "3      11.8      4.2        7.9",
            "4      12.7      4.6        8.4",
            "5      12.9      4.7        8.5",
            "",
            "Avg T1 = 12.6 +/- 0.5 us",
            "Avg T2* = 4.6 +/- 0.2 us",
            "",
            "!Excellent! T1 > 12us confirms Ne",
            "!substrate quality. Compare to He4",
            "!where T1 ~ 0.1us (factor 100x better)",
            "",
            "## Note: temperature excursion at 15:30",
            "## Pulse tube hiccup - data points 200-208",
            "## may be compromised. CHECK!",
        ]
    },
]

for page in pages:
    create_page(page["lines"], page["filename"])
    print(f"Created {page['filename']}")

print(f"\nAll pages saved to {OUTPUT_DIR}")
