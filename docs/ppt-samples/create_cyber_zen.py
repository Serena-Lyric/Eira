"""
Eira "Cyber Zen" (赛博景区) PPT Generator
Creates a 3-slide presentation using python-pptx with rich visuals,
gradients, shapes, and XML-level animations.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR_TYPE
from pptx.oxml.ns import qn, nsmap
from lxml import etree
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import copy
import math

# ─── Color Palette ───────────────────────────────────────────
DEEP_BASE = RGBColor(0x0D, 0x11, 0x17)       # #0D1117 深灰基底
NEON_GREEN = RGBColor(0x39, 0xFF, 0x14)       # #39FF14 荧光绿
SAKURA_PINK = RGBColor(0xFF, 0x79, 0xC6)      # #FF79C6 樱花粉
GOLD = RGBColor(0xFF, 0xD7, 0x00)             # #FFD700 金色
DARK_GREEN = RGBColor(0x0A, 0x2E, 0x1F)       # 墨绿
DARK_PURPLE = RGBColor(0x1A, 0x0A, 0x2E)     # 深紫
LIGHT_TEXT = RGBColor(0xC8, 0xD6, 0xE5)       # 浅灰文字
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_BG2 = RGBColor(0x16, 0x1B, 0x22)         # 稍亮的深色
CYAN_DIM = RGBColor(0x28, 0x9B, 0x8E)         # 暗青色点缀
ORANGE_ACCENT = RGBColor(0xFF, 0x8C, 0x42)    # 橙色点缀

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
IMG_DIR = r"D:\Application\ClaudeCode\repository\Eira\docs\ppt-samples\images"
os.makedirs(IMG_DIR, exist_ok=True)

# Chinese-compatible fonts (tried in order)
CN_FONT = 'Microsoft YaHei'
CN_FONT_BOLD = 'Microsoft YaHei'
print(f"Using font: {CN_FONT}")


# ═══════════════════════════════════════════════════════════════
#  IMAGE GENERATION (gradient backgrounds, decorative elements)
# ═══════════════════════════════════════════════════════════════

def hex_to_rgb(hex_str):
    """Convert hex color string to (R, G, B) tuple."""
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def create_dark_gradient_bg(width=1920, height=1080):
    """Create dark gradient background: deep gray with subtle ink-wash texture."""
    img = Image.new('RGBA', (width, height), hex_to_rgb('#0D1117') + (255,))
    draw = ImageDraw.Draw(img)

    # Subtle radial gradient from center (simulated with concentric ellipses)
    cx, cy = width // 2, height // 2
    max_radius = int(math.sqrt(cx*cx + cy*cy))
    for r in range(max_radius, 0, -3):
        alpha = int(6 * (1 - r / max_radius))
        if alpha <= 0:
            break
        # Shift color from dark green at center to purple at edges
        ratio = r / max_radius
        r_c = int(0x0D + (0x1A - 0x0D) * ratio)
        g_c = int(0x11 + (0x0A - 0x11) * ratio)
        b_c = int(0x17 + (0x2E - 0x17) * ratio)
        color = (r_c, g_c, b_c, alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Add subtle ink-wash texture: random faint brushstrokes
    import random
    random.seed(42)
    for _ in range(60):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        length = random.randint(80, 300)
        angle = random.uniform(0, 2 * math.pi)
        x2 = x1 + int(length * math.cos(angle))
        y2 = y1 + int(length * math.sin(angle))
        alpha = random.randint(3, 10)
        # Mix green and purple for ink-wash feel
        if random.random() < 0.5:
            color = (0x39, 0xFF, 0x14, alpha)
        else:
            color = (0xFF, 0x79, 0xC6, alpha)
        # Wider strokes for ink wash
        for offset in range(-2, 3):
            draw.line([(x1 + offset, y1), (x2 + offset, y2)],
                      fill=color, width=random.randint(1, 2))

    return img


def create_mountain_silhouette(width=800, height=400):
    """Create digital mountain silhouette - overlapping layered peaks."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Layer 1: back mountains (darkest, furthest)
    peaks = [
        [(0, 400), (60, 200), (150, 80), (250, 180), (350, 40), (450, 150),
         (550, 60), (650, 170), (750, 100), (800, 200)],
        [(0, 400), (100, 250), (200, 120), (300, 220), (400, 90), (500, 180),
         (600, 70), (700, 160), (800, 220)],
        [(0, 400), (80, 280), (180, 160), (280, 240), (400, 130), (520, 200),
         (620, 110), (720, 190), (800, 250)],
    ]

    colors = [
        (0x13, 0x2A, 0x1F, 180),  # dark green
        (0x1A, 0x25, 0x33, 200),  # dark blue-gray
        (0x0F, 0x1A, 0x25, 220),  # darkest
    ]

    for i, peak_list in enumerate(peaks):
        color = colors[i]
        # Draw filled polygon
        points = peak_list + [(800, 400), (0, 400)]
        draw.polygon(points, fill=color)

    # Layer 2: neon edge lines on some peaks (digital style)
    neon_peaks = [(350, 40), (450, 150), (550, 60), (500, 180), (600, 70)]
    for i in range(len(neon_peaks) - 1):
        draw.line([neon_peaks[i], neon_peaks[i+1]],
                  fill=(0x39, 0xFF, 0x14, 100), width=2)

    # Add a faint neon torii gate silhouette
    torii_cx, torii_bottom = 400, 380
    # Pillars
    draw.rectangle([torii_cx - 60, torii_bottom - 120, torii_cx - 40, torii_bottom],
                   fill=(0x39, 0xFF, 0x14, 60))
    draw.rectangle([torii_cx + 40, torii_bottom - 120, torii_cx + 60, torii_bottom],
                   fill=(0x39, 0xFF, 0x14, 60))
    # Top beam
    draw.rectangle([torii_cx - 80, torii_bottom - 130, torii_cx + 80, torii_bottom - 115],
                   fill=(0x39, 0xFF, 0x14, 80))
    # Upper beam (slightly curved effect via wider rectangle)
    draw.rectangle([torii_cx - 75, torii_bottom - 145, torii_cx + 75, torii_bottom - 130],
                   fill=(0x39, 0xFF, 0x14, 50))

    return img


def create_tech_lines_bg(width=1920, height=200):
    """Create flowing data stream lines for tech feel."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Flowing lines like data streams
    import random
    random.seed(123)
    for i in range(30):
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        # Create a flowing path
        points = [(start_x, start_y)]
        x, y = start_x, start_y
        for _ in range(random.randint(8, 25)):
            x += random.randint(-30, 50)
            y += random.randint(-15, 20)
            points.append((x % width, y % height))

        # Draw the flowing line
        color = random.choice([
            (0x39, 0xFF, 0x14, random.randint(15, 50)),
            (0xFF, 0x79, 0xC6, random.randint(10, 40)),
            (0x28, 0x9B, 0x8E, random.randint(10, 30)),
        ])
        for j in range(len(points) - 1):
            draw.line([points[j], points[j+1]], fill=color, width=random.randint(1, 2))

    return img


def create_golden_particles(width=1920, height=1080):
    """Create floating golden particles (sakura-petal-like)."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    import random
    random.seed(99)
    for _ in range(50):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.randint(2, 8)
        alpha = random.randint(30, 120)
        color = random.choice([
            (0xFF, 0xD7, 0x00, alpha),
            (0xFF, 0x79, 0xC6, alpha),
            (0x39, 0xFF, 0x14, alpha // 2),
        ])
        # Draw as small ellipse (petal shape)
        draw.ellipse([x, y, x + size, y + size * 2], fill=color)
        draw.ellipse([x, y, x + size * 2, y + size], fill=color)

    return img


def create_neon_torii(width=200, height=300):
    """Create a neon torii gate icon."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Glow effect layers
    for glow in range(4, 0, -1):
        alpha = 30 // glow
        color = (0x39, 0xFF, 0x14, alpha)
        w_offset = glow * 2
        # Pillars
        draw.rectangle([50 - w_offset, 100, 70 + w_offset, 280], fill=color)
        draw.rectangle([130 - w_offset, 100, 150 + w_offset, 280], fill=color)
        # Top beam
        draw.rectangle([30 - w_offset, 85, 170 + w_offset, 105 + w_offset], fill=color)
        # Upper beam
        draw.rectangle([40 - w_offset, 70, 160 + w_offset, 88 + w_offset], fill=color)

    # Core neon lines
    draw.rectangle([50, 100, 70, 280], fill=(0x39, 0xFF, 0x14, 200))
    draw.rectangle([130, 100, 150, 280], fill=(0x39, 0xFF, 0x14, 200))
    draw.rectangle([30, 85, 170, 105], fill=(0x39, 0xFF, 0x14, 220))
    draw.rectangle([40, 70, 160, 88], fill=(0x39, 0xFF, 0x14, 180))

    return img


def create_layer_indicator(width=40, height=40, color_hex="#39FF14"):
    """Create a small glowing dot for architecture layer indicators."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rgb = hex_to_rgb(color_hex)

    # Glow circles
    for r in range(width // 2, 3, -2):
        alpha = max(0, int(100 * (1 - r / (width/2))))
        draw.ellipse([width//2 - r, height//2 - r, width//2 + r, height//2 + r],
                     fill=rgb + (alpha,))

    # Core dot
    draw.ellipse([width//2 - 5, height//2 - 5, width//2 + 5, height//2 + 5],
                 fill=rgb + (220,))

    return img


def create_gradient_rect(width=1920, height=1080):
    """Create a full-slide gradient rectangle image (for slide background)."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Diagonal gradient from bottom-left (dark green) to top-right (dark purple)
    for y in range(height):
        for x in range(0, width, 4):  # step for performance
            x_ratio = x / width
            y_ratio = y / height
            # Blend based on position
            blend = (x_ratio + y_ratio) / 2

            r = int(0x0A + (0x1A - 0x0A) * blend + (0x0D - 0x0A) * (1 - abs(blend - 0.5) * 2))
            g = int(0x2E + (0x0A - 0x2E) * blend + (0x11 - 0x2E) * (1 - abs(blend - 0.5) * 2))
            b = int(0x1F + (0x2E - 0x1F) * blend + (0x17 - 0x1F) * (1 - abs(blend - 0.5) * 2))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            # Draw a horizontal line for performance
            draw.line([(x, y), (min(x + 4, width - 1), y)], fill=(r, g, b, 255))

    return img


# ═══════════════════════════════════════════════════════════════
#  IMAGE GENERATION - Pre-render
# ═══════════════════════════════════════════════════════════════

print("Generating images...")
dark_bg = create_dark_gradient_bg(1920, 1080)
dark_bg.save(os.path.join(IMG_DIR, 'bg_dark_gradient.png'), 'PNG')

gradient_rect = create_gradient_rect(1920, 1080)
gradient_rect.save(os.path.join(IMG_DIR, 'gradient_rect.png'), 'PNG')

mountains = create_mountain_silhouette(800, 400)
mountains.save(os.path.join(IMG_DIR, 'mountains.png'), 'PNG')

tech_lines = create_tech_lines_bg(1920, 200)
tech_lines.save(os.path.join(IMG_DIR, 'tech_lines.png'), 'PNG')

particles = create_golden_particles(1920, 1080)
particles.save(os.path.join(IMG_DIR, 'particles.png'), 'PNG')

neon_torii = create_neon_torii(200, 300)
neon_torii.save(os.path.join(IMG_DIR, 'neon_torii.png'), 'PNG')

# Layer indicators for architecture slide
for i, color in enumerate(["#39FF14", "#FF79C6", "#FFD700", "#289B8E", "#FF8C42"]):
    dot = create_layer_indicator(40, 40, color)
    dot.save(os.path.join(IMG_DIR, f'layer_dot_{i}.png'), 'PNG')

print("All images generated.")


# ═══════════════════════════════════════════════════════════════
#  PPTX HELPERS
# ═══════════════════════════════════════════════════════════════

def set_slide_bg(slide, r, g, b):
    """Set solid background color for a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(r, g, b)


def add_bg_image(slide, img_path):
    """Add a full-slide background image."""
    left = Emu(0)
    top = Emu(0)
    width = Emu(12192000)  # 13.333 inches in EMU
    height = Emu(6858000)  # 7.5 inches in EMU
    slide.shapes.add_picture(img_path, left, top, width, height)


def add_text_box(slide, left, top, width, height, text, font_size=14,
                 color=LIGHT_TEXT, bold=False, alignment=PP_ALIGN.LEFT,
                 font_name=CN_FONT, anchor=MSO_ANCHOR.TOP, line_spacing=1.2):
    """Add a text box with formatted text."""
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                     Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size = None

    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    # Also set East Asian font for Chinese character rendering
    pPr = p._p.get_or_add_pPr()
    defRPr = pPr.get_or_add_defRPr()
    ea = etree.SubElement(defRPr, qn('a:ea'))
    ea.set('typeface', font_name)
    p.alignment = alignment
    p.space_after = Pt(0)
    p.space_before = Pt(0)
    # Line spacing (reuse pPr from above)
    lnSpc = etree.SubElement(pPr, qn('a:lnSpc'))
    spcPct = etree.SubElement(lnSpc, qn('a:spcPct'))
    spcPct.set('val', str(int(line_spacing * 100000)))

    return txBox


def add_multiline_text(slide, left, top, width, height, lines,
                       font_name=CN_FONT, anchor=MSO_ANCHOR.TOP):
    """Add a text box with multiple formatted paragraphs.
    lines: list of dicts with 'text', 'font_size', 'color', 'bold', 'alignment', 'line_spacing'
    """
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                     Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size = None

    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.text = line.get('text', '')
        p.font.size = Pt(line.get('font_size', 14))
        p.font.color.rgb = line.get('color', LIGHT_TEXT)
        p.font.bold = line.get('bold', False)
        p.font.name = line.get('font_name', font_name)
        # Also set East Asian font for Chinese character rendering
        pPr = p._p.get_or_add_pPr()
        defRPr = pPr.get_or_add_defRPr()
        ea = etree.SubElement(defRPr, qn('a:ea'))
        ea.set('typeface', line.get('font_name', font_name))

        p.alignment = line.get('alignment', PP_ALIGN.LEFT)
        p.space_after = Pt(line.get('space_after', 4))
        p.space_before = Pt(line.get('space_before', 0))

        # Line spacing (reuse pPr from above)
        ls = line.get('line_spacing', 1.3)
        lnSpc = etree.SubElement(pPr, qn('a:lnSpc'))
        spcPct = etree.SubElement(lnSpc, qn('a:spcPct'))
        spcPct.set('val', str(int(ls * 100000)))

    return txBox


def add_rect(slide, left, top, width, height, fill_color=None,
             line_color=None, line_width=None, corner_radius=None):
    """Add a rectangle shape."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if corner_radius else MSO_SHAPE.RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.line.fill.background()
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()

    if line_color:
        shape.line.color.rgb = line_color
        shape.line.fill.solid()
        if line_width:
            shape.line.width = Pt(line_width)

    return shape


def add_neon_rect(slide, left, top, width, height, color=NEON_GREEN, line_width=1.5):
    """Add a rectangle with neon border effect (no fill)."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.background()
    shape.line.color.rgb = color
    shape.line.width = Pt(line_width)
    shape.line.fill.solid()
    return shape


def add_line_decor(slide, x1, y1, x2, y2, color=NEON_GREEN, width=1.5):
    """Add a decorative line."""
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    connector.line.color.rgb = color
    connector.line.width = Pt(width)
    connector.line.fill.solid()
    return connector


# ═══════════════════════════════════════════════════════════════
#  ANIMATION HELPERS (XML-level)
# ═══════════════════════════════════════════════════════════════

def get_shape_diagram_name(shape):
    """Get the XML element name used to address this shape from the timing element."""
    spTree = shape._element.getparent()
    # Find index in spTree
    ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
    shapes = spTree.findall('.//p:sp', ns)
    for idx, sp in enumerate(shapes):
        if sp == shape._element:
            return idx + 1  # 1-based
    return 1


def add_fade_animation(shape, delay=0, duration=0.5):
    """Add a simple fade-in animation to a shape. Uses p:animEffect."""
    sp_id = shape.shape_id

    # Get or create timing element
    slide_elem = shape._element
    while slide_elem.tag != qn('p:sld'):
        slide_elem = slide_elem.getparent()

    # Find or create timing
    timing = slide_elem.find('.//' + qn('p:timing'))
    if timing is None:
        timing = etree.SubElement(slide_elem, qn('p:timing'))

    # Find or create tnLst
    tnLst = timing.find('.//' + qn('p:tnLst'))
    if tnLst is None:
        tnLst = etree.SubElement(timing, qn('p:tnLst'))

    # Create a parallel time node
    par = etree.SubElement(tnLst, qn('p:par'))

    # Condition: on click
    cond = etree.SubElement(par, qn('p:cond'))
    cond.set('delay', str(int(delay * 1000)))

    # Child time node - animate effect
    cTn = etree.SubElement(par, qn('p:cTn'))
    cTn.set('id', str(sp_id + 100))
    cTn.set('dur', str(int(duration * 1000)))
    cTn.set('fill', 'hold')

    # Target
    tgtEl = etree.SubElement(cTn, qn('p:tgtEl'))
    spTgt = etree.SubElement(tgtEl, qn('p:spTgt'))
    spTgt.set('spid', str(sp_id))

    # Animate: fade in
    anim = etree.SubElement(cTn, qn('p:animEffect'))
    anim.set('transition', 'in')
    anim.set('filter', 'fade')

    # Set behavior
    setBhvr = etree.SubElement(anim, qn('p:setBhvr'))
    to = etree.SubElement(setBhvr, qn('p:to'))
    to_elem = etree.SubElement(to, qn('p:alphaModFix'))
    to_elem.set('amt', '100000')  # fully visible


def add_animation_sequence(slide, shapes_data):
    """Add a sequence of fade animations to multiple shapes.
    shapes_data: list of (shape, delay_seconds) tuples.
    All animations start "with previous" after the initial click.
    """
    slide_elem = slide._element
    ns_p = 'http://schemas.openxmlformats.org/presentationml/2006/main'

    # Find or create timing
    timing = slide_elem.find('.//' + qn('p:timing'))
    if timing is None:
        timing = etree.SubElement(slide_elem, qn('p:timing'))

    tnLst = timing.find('.//' + qn('p:tnLst'))
    if tnLst is None:
        tnLst = etree.SubElement(timing, qn('p:tnLst'))

    # Create sequence - first shape on click, rest "with previous" after delay
    seq = etree.SubElement(tnLst, qn('p:seq'))
    seq.set('concurrent', '0')
    seq.set('nextAc', 'last')

    # Condition: on click
    cond = etree.SubElement(seq, qn('p:cond'))
    cond.set('delay', '0')

    for shape, delay in shapes_data:
        sp_id = shape.shape_id

        # Create parallel time node for each shape animation
        par = etree.SubElement(seq, qn('p:par'))

        # Delay
        cTn = etree.SubElement(par, qn('p:cTn'))
        cTn.set('id', str(sp_id + 200))
        cTn.set('dur', '500')  # 0.5s fade
        cTn.set('fill', 'hold')

        # Delay before this shape
        stCondLst = etree.SubElement(cTn, qn('p:stCondLst'))
        delay_cond = etree.SubElement(stCondLst, qn('p:cond'))
        delay_cond.set('delay', str(int(delay * 1000)))

        # Target
        tgtEl = etree.SubElement(cTn, qn('p:tgtEl'))
        spTgt = etree.SubElement(tgtEl, qn('p:spTgt'))
        spTgt.set('spid', str(sp_id))

        # Animate effect - fade in
        anim = etree.SubElement(cTn, qn('p:animEffect'))
        anim.set('transition', 'in')
        anim.set('filter', 'fade')

        setBhvr = etree.SubElement(anim, qn('p:setBhvr'))
        to = etree.SubElement(setBhvr, qn('p:to'))
        to_elem = etree.SubElement(to, qn('p:alphaModFix'))
        to_elem.set('amt', '100000')


# ═══════════════════════════════════════════════════════════════
#  SLIDE 1: COVER PAGE
# ═══════════════════════════════════════════════════════════════

def create_cover_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    anim_shapes = []  # Collect (shape, delay) for animation sequence

    # Background
    add_bg_image(slide, os.path.join(IMG_DIR, 'bg_dark_gradient.png'))
    add_bg_image(slide, os.path.join(IMG_DIR, 'particles.png'))

    # Mountains at bottom
    s = slide.shapes.add_picture(os.path.join(IMG_DIR, 'mountains.png'),
                             Inches(0), Inches(4.8), Inches(13.333), Inches(2.7))
    anim_shapes.append((s, 0.3))

    # Tech lines overlay (subtle)
    slide.shapes.add_picture(os.path.join(IMG_DIR, 'tech_lines.png'),
                             Inches(0), Inches(0), Inches(13.333), Inches(1.2))

    # Decorative corner brackets - top left
    add_line_decor(slide, 0.5, 0.4, 0.5, 1.0, NEON_GREEN, 2.0)
    add_line_decor(slide, 0.5, 0.4, 1.1, 0.4, NEON_GREEN, 2.0)

    # Decorative corner brackets - bottom right
    add_line_decor(slide, 12.3, 6.6, 12.3, 7.0, NEON_GREEN, 2.0)
    add_line_decor(slide, 12.3, 7.0, 12.833, 7.0, NEON_GREEN, 2.0)

    # Accent line under title area (sakura pink, left side)
    s = add_line_decor(slide, 1.5, 3.0, 4.5, 3.0, SAKURA_PINK, 3.0)
    anim_shapes.append((s, 0.8))

    # Main title "Eira"
    title_lines = [
        {'text': 'Eira', 'font_size': 80, 'color': WHITE, 'bold': True,
         'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.0, 'space_after': 0},
        {'text': '_________________________________', 'font_size': 8, 'color': NEON_GREEN,
         'bold': False, 'alignment': PP_ALIGN.LEFT, 'line_spacing': 0.6, 'space_after': 6},
        {'text': 'AI 数字人景区导览系统', 'font_size': 26, 'color': LIGHT_TEXT, 'bold': False,
         'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.2, 'space_after': 4},
        {'text': 'Live2D 二次元角色  ×  多模态语音交互  ×  RAG 知识增强', 'font_size': 14, 'color': SAKURA_PINK,
         'bold': False, 'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.3, 'space_after': 12},
        {'text': '"中国软件杯"大学生软件设计大赛  | 赛博景区 · Cyber Zen', 'font_size': 12, 'color': GOLD,
         'bold': False, 'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.3, 'space_after': 0},
    ]
    s = add_multiline_text(slide, 1.5, 1.8, 7.0, 3.5, title_lines)
    anim_shapes.insert(0, (s, 0.0))  # Title first

    # Neon torii icon - right side
    s = slide.shapes.add_picture(os.path.join(IMG_DIR, 'neon_torii.png'),
                             Inches(10.0), Inches(1.8), Inches(2.5), Inches(3.8))
    anim_shapes.append((s, 0.5))

    # Small decorative dots
    for x, y, c in [(11.5, 5.8, NEON_GREEN), (11.8, 5.5, SAKURA_PINK), (12.1, 5.2, GOLD)]:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                                     Inches(x), Inches(y), Inches(0.1), Inches(0.1))
        dot.fill.solid()
        dot.fill.fore_color.rgb = c
        dot.line.fill.background()

    # Bottom info bar
    info_rect = add_rect(slide, 0, 6.6, 13.333, 0.9, fill_color=RGBColor(0x0D, 0x11, 0x17))
    # Make it semi-transparent by setting alpha via XML
    solidFill = info_rect._element.find('.//' + qn('a:solidFill'))
    if solidFill is not None:
        srgb = solidFill.find(qn('a:srgbClr'))
        if srgb is not None:
            alpha = etree.SubElement(srgb, qn('a:alpha'))
            alpha.set('val', '70000')  # 70% opacity

    info_lines = [
        {'text': '赛博景区  ·  Cyber Zen  ·  数字山水', 'font_size': 11, 'color': NEON_GREEN,
         'bold': False, 'alignment': PP_ALIGN.CENTER, 'line_spacing': 1.2, 'space_after': 0},
    ]
    s = add_multiline_text(slide, 0, 6.75, 13.333, 0.4, info_lines)
    anim_shapes.append((s, 1.0))

    # Left side glowing vertical accent bar
    accent_bar = add_rect(slide, 0.2, 0, 0.06, 7.5, fill_color=NEON_GREEN)
    accent_bar.line.fill.background()
    anim_shapes.append((accent_bar, 0.1))

    # Apply animations
    add_animation_sequence(slide, anim_shapes)

    return slide


# ═══════════════════════════════════════════════════════════════
#  SLIDE 2: CORE HIGHLIGHTS
# ═══════════════════════════════════════════════════════════════

def create_highlights_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    anim_shapes = []

    # Background
    add_bg_image(slide, os.path.join(IMG_DIR, 'bg_dark_gradient.png'))
    add_bg_image(slide, os.path.join(IMG_DIR, 'particles.png'))

    # Top decorative line
    add_line_decor(slide, 1.0, 0.4, 12.333, 0.4, NEON_GREEN, 1.0)

    # Title section
    title_box = add_rect(slide, 0.8, 0.6, 5.0, 0.8, fill_color=RGBColor(0x39, 0xFF, 0x14))
    # Make fill semi-transparent
    solidFill = title_box._element.find('.//' + qn('a:solidFill'))
    if solidFill is not None:
        srgb = solidFill.find(qn('a:srgbClr'))
        if srgb is not None:
            alpha = etree.SubElement(srgb, qn('a:alpha'))
            alpha.set('val', '15000')  # 15% opacity

    title_lines = [
        {'text': '✦  核心亮点', 'font_size': 28, 'color': WHITE, 'bold': True,
         'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.1, 'space_after': 0},
    ]
    s = add_multiline_text(slide, 1.0, 0.65, 5.0, 0.7, title_lines)
    anim_shapes.append((s, 0.0))

    # Subtitle
    s = add_text_box(slide, 1.0, 1.4, 8.0, 0.5,
                 '打造景区 AI 导览新体验 — 多模态交互 × 实时响应 × 沉浸式数字人',
                 font_size=13, color=LIGHT_TEXT, bold=False)
    anim_shapes.append((s, 0.2))

    # 5 highlight cards in a row
    highlights = [
        {
            'icon': '🔊',
            'title': '多模态交互',
            'desc': '语音 + 文字双通道\n实时语音识别(ASR)\n情感化语音合成(TTS)',
            'accent': NEON_GREEN,
        },
        {
            'icon': '🎭',
            'title': 'Live2D 数字人',
            'desc': '二次元角色实时渲染\n嘴型同步+表情联动\n拖拽旋转 3D 视角',
            'accent': SAKURA_PINK,
        },
        {
            'icon': '🧠',
            'title': 'RAG 知识库',
            'desc': '景区知识智能检索\n向量化语义匹配\n精准回答海量问题',
            'accent': GOLD,
        },
        {
            'icon': '⚡',
            'title': '流式响应',
            'desc': 'WebSocket 实时通信\n语音流式推送\n毫秒级首字延迟',
            'accent': CYAN_DIM,
        },
        {
            'icon': '🌐',
            'title': '7×24 在线',
            'desc': '全天候智能服务\n无需人工值守\n多语言多景区适配',
            'accent': ORANGE_ACCENT,
        },
    ]

    card_w = 2.2
    card_h = 3.8
    start_x = 0.8
    gap = 0.2
    card_y = 2.3

    for i, h in enumerate(highlights):
        x = start_x + i * (card_w + gap)
        delay = 0.4 + i * 0.15  # Stagger cards left to right

        # Card background
        card = add_rect(slide, x, card_y, card_w, card_h,
                        fill_color=DARK_BG2, line_color=h['accent'], line_width=1.0,
                        corner_radius=0.1)
        anim_shapes.append((card, delay))

        # Top accent stripe
        stripe = add_rect(slide, x + 0.2, card_y + 0.15, card_w - 0.4, 0.04,
                          fill_color=h['accent'])
        stripe.line.fill.background()

        # Number - large, transparent
        num_lines = [
            {'text': f'0{i+1}', 'font_size': 36, 'color': h['accent'], 'bold': True,
             'alignment': PP_ALIGN.CENTER, 'line_spacing': 1.0, 'space_after': 4},
        ]
        num_box = add_multiline_text(slide, x + 0.3, card_y + 0.35, card_w - 0.6, 0.6, num_lines)

        # Title
        card_title = [
            {'text': h['title'], 'font_size': 15, 'color': WHITE, 'bold': True,
             'alignment': PP_ALIGN.CENTER, 'line_spacing': 1.2, 'space_after': 6},
        ]
        add_multiline_text(slide, x + 0.15, card_y + 1.1, card_w - 0.3, 0.5, card_title)

        # Description
        card_desc = [
            {'text': h['desc'], 'font_size': 10, 'color': LIGHT_TEXT, 'bold': False,
             'alignment': PP_ALIGN.CENTER, 'line_spacing': 1.6, 'space_after': 0},
        ]
        add_multiline_text(slide, x + 0.2, card_y + 1.7, card_w - 0.4, 1.8, card_desc)

        # Bottom accent dot
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                                     Inches(x + card_w/2 - 0.08), Inches(card_y + card_h - 0.35),
                                     Inches(0.16), Inches(0.16))
        dot.fill.solid()
        dot.fill.fore_color.rgb = h['accent']
        dot.line.fill.background()

    # Bottom quote bar
    s = add_line_decor(slide, 1.0, 6.5, 12.333, 6.5, SAKURA_PINK, 1.0)
    anim_shapes.append((s, 1.3))
    quote = [
        {'text': '"让每一位游客都拥有专属的 AI 导游，在数字山水中感受赛博景区的魅力"',
         'font_size': 12, 'color': GOLD, 'bold': False, 'alignment': PP_ALIGN.CENTER,
         'line_spacing': 1.3, 'space_after': 0},
    ]
    s = add_multiline_text(slide, 2.0, 6.65, 9.333, 0.5, quote)
    anim_shapes.append((s, 1.4))

    # Left accent bar
    accent_bar = add_rect(slide, 0.2, 0, 0.06, 7.5, fill_color=NEON_GREEN)
    accent_bar.line.fill.background()

    # Apply animations
    add_animation_sequence(slide, anim_shapes)

    return slide


# ═══════════════════════════════════════════════════════════════
#  SLIDE 3: TECH ARCHITECTURE
# ═══════════════════════════════════════════════════════════════

def create_architecture_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    anim_shapes = []

    # Background
    add_bg_image(slide, os.path.join(IMG_DIR, 'bg_dark_gradient.png'))
    add_bg_image(slide, os.path.join(IMG_DIR, 'particles.png'))

    # Tech lines at bottom
    slide.shapes.add_picture(os.path.join(IMG_DIR, 'tech_lines.png'),
                             Inches(0), Inches(5.5), Inches(13.333), Inches(2.0))

    # Title
    add_line_decor(slide, 1.0, 0.4, 12.333, 0.4, NEON_GREEN, 1.0)

    title_box = add_rect(slide, 0.8, 0.6, 6.0, 0.8)
    solidFill = title_box._element.find('.//' + qn('a:solidFill'))
    if solidFill is not None:
        srgb = solidFill.find(qn('a:srgbClr'))
        if srgb is not None:
            alpha = etree.SubElement(srgb, qn('a:alpha'))
            alpha.set('val', '15000')
    title_lines = [
        {'text': '⬡  技术架构', 'font_size': 28, 'color': WHITE, 'bold': True,
         'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.1, 'space_after': 0},
    ]
    s = add_multiline_text(slide, 1.0, 0.65, 6.0, 0.7, title_lines)
    anim_shapes.append((s, 0.0))

    s = add_text_box(slide, 1.0, 1.4, 10.0, 0.4,
                 '五层架构设计 — 从用户交互到底层 AI 服务，构建可扩展的数字人导览系统',
                 font_size=12, color=LIGHT_TEXT, bold=False)
    anim_shapes.append((s, 0.2))

    # Architecture layers (bottom-up)
    layers = [
        {
            'name': 'L5 · AI 服务层',
            'items': 'LLM 大语言模型  |  ASR 语音识别  |  TTS 语音合成  |  Embedding 向量化  |  Search 语义检索',
            'color': ORANGE_ACCENT,
            'color_hex': '#FF8C42',
            'y': 5.6,
        },
        {
            'name': 'L4 · 数据层',
            'items': 'PostgreSQL 关系存储  |  Redis 缓存/会话  |  阿里云 OSS 资产存储  |  Milvus 向量数据库',
            'color': CYAN_DIM,
            'color_hex': '#289B8E',
            'y': 4.55,
        },
        {
            'name': 'L3 · 应用层',
            'items': 'Chat 对话引擎  |  Voice 语音处理  |  Persona 角色管理  |  Knowledge 知识库  |  Admin 管理后台',
            'color': GOLD,
            'color_hex': '#FFD700',
            'y': 3.5,
        },
        {
            'name': 'L2 · 前端层',
            'items': 'Vue 3 + TypeScript  |  Live2D Cubism 5 渲染  |  WebSocket 双向通信  |  响应式管理界面',
            'color': SAKURA_PINK,
            'color_hex': '#FF79C6',
            'y': 2.45,
        },
        {
            'name': 'L1 · 接入层',
            'items': '游客端 (web-user)  |  管理端 (web-admin)  |  Nginx 反向代理  |  CORS 跨域安全  |  JWT 认证',
            'color': NEON_GREEN,
            'color_hex': '#39FF14',
            'y': 1.7,
        },
    ]

    layer_h = 0.8
    layer_w = 11.5
    layer_x = 1.0

    for i, layer in enumerate(layers):
        y = layer['y']
        color = layer['color']
        delay = 0.3 + (4 - i) * 0.12  # Bottom-up stagger (L5 first, L1 last)

        # Layer background rectangle with gradient-like effect
        rect = add_rect(slide, layer_x, y, layer_w, layer_h,
                        fill_color=DARK_BG2, line_color=color, line_width=1.2,
                        corner_radius=0.08)
        anim_shapes.append((rect, delay))

        # Left color stripe
        stripe = add_rect(slide, layer_x, y, 0.06, layer_h, fill_color=color)
        stripe.line.fill.background()

        # Layer indicator dot
        dot_img = os.path.join(IMG_DIR, f'layer_dot_{i}.png')
        slide.shapes.add_picture(dot_img,
                                 Inches(layer_x + 0.2), Inches(y + 0.2),
                                 Inches(0.4), Inches(0.4))

        # Layer name
        name_lines = [
            {'text': layer['name'], 'font_size': 12, 'color': color, 'bold': True,
             'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.0, 'space_after': 0},
        ]
        add_multiline_text(slide, layer_x + 0.75, y + 0.08, 2.5, 0.35, name_lines)

        # Layer items
        item_lines = [
            {'text': layer['items'], 'font_size': 9, 'color': LIGHT_TEXT, 'bold': False,
             'alignment': PP_ALIGN.LEFT, 'line_spacing': 1.2, 'space_after': 0},
        ]
        add_multiline_text(slide, layer_x + 0.75, y + 0.4, layer_w - 1.0, 0.35, item_lines)

        # Right-side decorative bracket
        add_line_decor(slide, layer_x + layer_w - 0.3, y + 0.2,
                       layer_x + layer_w - 0.3, y + 0.6, color, 1.0)

        # Connecting lines between layers (except from L5)
        if i < len(layers) - 1:
            next_y = layers[i + 1]['y']
            mid_x = layer_x + layer_w / 2
            # Vertical connector
            s_conn = add_line_decor(slide, mid_x - 0.15 + (i * 0.08), y + layer_h,
                           mid_x - 0.15 + (i * 0.08), next_y, color, 0.8)
            anim_shapes.append((s_conn, delay + 0.05))

    # Right side: technology stack summary
    summary_x = 1.0
    summary_y = 6.5
    summary_lines = [
        {'text': '技术栈:',
         'font_size': 11, 'color': NEON_GREEN, 'bold': True, 'space_after': 2},
        {'text': 'Python FastAPI  ·  Vue 3  ·  Live2D Cubism 5  ·  WebSocket  ·  PostgreSQL  ·  Milvus  ·  Docker',
         'font_size': 10, 'color': LIGHT_TEXT, 'bold': False, 'space_after': 0},
    ]
    s = add_multiline_text(slide, summary_x, summary_y, 11.0, 0.6, summary_lines)
    anim_shapes.append((s, 1.0))

    # Left accent bar
    accent_bar = add_rect(slide, 0.2, 0, 0.06, 7.5, fill_color=NEON_GREEN)
    accent_bar.line.fill.background()

    # Apply animations
    add_animation_sequence(slide, anim_shapes)

    return slide


# ═══════════════════════════════════════════════════════════════
#  MAIN ASSEMBLY
# ═══════════════════════════════════════════════════════════════

def main():
    print("Creating presentation...")
    prs = Presentation()

    # Set 16:9 widescreen
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)

    # Create slides
    s1 = create_cover_slide(prs)
    print("  Slide 1: Cover page done")

    s2 = create_highlights_slide(prs)
    print("  Slide 2: Core highlights done")

    s3 = create_architecture_slide(prs)
    print("  Slide 3: Tech architecture done")

    # Save
    output_path = r"D:\Application\ClaudeCode\repository\Eira\docs\ppt-samples\方向C-赛博景区.pptx"
    prs.save(output_path)
    print(f"\nPresentation saved to: {output_path}")
    print("Done!")


if __name__ == '__main__':
    main()
