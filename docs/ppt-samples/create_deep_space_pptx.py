"""
Eira Deep Space Orbit PPT Generator
深空星轨风格演示文稿 —— 中国软件杯参赛项目
"""

import os
import math
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from pptx import Presentation
from pptx.util import Inches, Pt, Emu, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR_TYPE
from pptx.oxml.ns import qn, nsmap
from lxml import etree

# ── Colors ────────────────────────────────────────────
BG_DEEP   = (10, 14, 39)       # #0A0E27
BG_MID    = (26, 31, 58)       # #1A1F3A
GOLD      = (240, 192, 96)     # #F0C060
BLUE_SOFT = (128, 200, 255)    # #80C8FF
WHITE_DIM = (200, 210, 230)    # subtle white
WHITE_BRIGHT = (240, 245, 255)
STAR_COLOR = (180, 200, 240)
ACCENT_DARK  = (40, 50, 80)
ACCENT_PURPLE = (100, 80, 180)  # subtle purple tint

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
SLIDE_W_PX = 1920
SLIDE_H_PX = 1080

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
# PART 1: Background Image Generation
# ═══════════════════════════════════════════════════════════════

def create_starfield_bg(width=SLIDE_W_PX, height=SLIDE_H_PX, seed=42):
    """Generate a deep space background with gradient, stars, and orbital elements."""
    random.seed(seed)
    img = Image.new('RGB', (width, height), BG_DEEP)
    pixels = img.load()

    # ── Vertical gradient: deep blue → slightly lighter blue ──
    for y in range(height):
        ratio = y / height
        r = int(BG_DEEP[0] + (BG_MID[0] - BG_DEEP[0]) * ratio)
        g = int(BG_DEEP[1] + (BG_MID[1] - BG_DEEP[1]) * ratio)
        b = int(BG_DEEP[2] + (BG_MID[2] - BG_DEEP[2]) * ratio)
        for x in range(width):
            pixels[x, y] = (r, g, b)

    # ── Subtle radial glow at center ──
    cx, cy = width // 2, height // 2
    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            max_dist = math.sqrt(cx**2 + cy**2)
            glow = max(0, 1.0 - (dist / max_dist)**0.5) * 0.08
            if glow > 0:
                r, g, b = pixels[x, y]
                pixels[x, y] = (
                    min(255, int(r + glow * 40)),
                    min(255, int(g + glow * 30)),
                    min(255, int(b + glow * 50)),
                )

    # ── Large faint nebula patches ──
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    for _ in range(3):
        nx = random.randint(width//4, 3*width//4)
        ny = random.randint(height//4, 3*height//4)
        nr = random.randint(200, 500)
        for i in range(nr, 0, -20):
            alpha = max(1, int(3 * (1 - i/nr)))
            color = random.choice([
                (40, 30, 80, alpha),
                (30, 40, 70, alpha),
                (50, 30, 60, alpha),
            ])
            draw_overlay.ellipse([nx-i, ny-i, nx+i, ny+i], fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=40))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    # ── Stars (various sizes & brightness) ──
    draw = ImageDraw.Draw(img)
    for _ in range(400):
        sx = random.randint(0, width - 1)
        sy = random.randint(0, height - 1)
        size = random.random() * 2.5
        brightness = random.randint(60, 255)
        alpha = random.randint(30, 255)
        color = (brightness, brightness, min(255, brightness + 40))

        # Star glow
        for r in range(int(size * 4), 0, -1):
            a = max(1, int(alpha * (1.0 - r / (size * 4 + 1)) * 0.3))
            temp = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(temp)
            tdraw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(*color, a))
            img = Image.alpha_composite(img.convert('RGBA'), temp).convert('RGB')

    # ── Larger bright stars with cross flare ──
    for _ in range(12):
        sx = random.randint(50, width - 50)
        sy = random.randint(50, height - 50)
        c = random.randint(200, 255)
        draw = ImageDraw.Draw(img)
        # Cross flare
        flare_len = random.randint(8, 20)
        flare_alpha = random.randint(40, 100)
        for d in range(flare_len):
            a = max(1, int(flare_alpha * (1 - d/flare_len)))
            for dx, dy in [(d, 0), (-d, 0), (0, d), (0, -d)]:
                if 0 <= sx+dx < width and 0 <= sy+dy < height:
                    draw.point((sx+dx, sy+dy), fill=(c, c, min(255, c+30)))
        # Center dot
        draw.ellipse([sx-2, sy-2, sx+2, sy+2], fill=(255, 255, 255))

    return img


def create_cover_bg():
    """Cover slide background with prominent orbital ring."""
    img = create_starfield_bg()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2

    # ── Large orbital ring (ellipse) ──
    ring_rx = int(w * 0.38)
    ring_ry = int(h * 0.28)

    # Draw orbital ring as a thin ellipse outline
    for angle in range(0, 360, 1):
        rad = math.radians(angle)
        x = cx + ring_rx * math.cos(rad)
        y = cy + ring_ry * math.sin(rad) - int(h * 0.06)
        # Vary brightness along the ring
        bright = 40 + int(30 * abs(math.sin(rad * 2)))
        for px in range(-2, 3):
            for py in range(-2, 3):
                if math.sqrt(px**2 + py**2) <= 2:
                    xi, yi = int(x) + px, int(y) + py
                    if 0 <= xi < w and 0 <= yi < h:
                        existing = img.getpixel((xi, yi))
                        blend = min(255, existing[0] + bright, existing[1] + bright, existing[2] + bright)
                        draw.point((xi, yi), fill=(blend, blend, min(255, blend + 30)))

    # Second thinner ring
    ring2_rx = int(w * 0.42)
    ring2_ry = int(h * 0.32)
    for angle in range(0, 360, 2):
        rad = math.radians(angle)
        x = cx + ring2_rx * math.cos(rad)
        y = cy + ring2_ry * math.sin(rad) - int(h * 0.05)
        bright = 20 + int(15 * abs(math.cos(rad * 3)))
        draw.point((int(x), int(y)), fill=(bright+20, bright+15, bright+40))

    # ── Glowing nodes on the ring ──
    node_angles = [30, 120, 210, 300]
    for angle_deg in node_angles:
        rad = math.radians(angle_deg)
        nx = cx + ring_rx * math.cos(rad)
        ny = cy + ring_ry * math.sin(rad) - int(h * 0.06)
        for r in range(8, 0, -2):
            alpha = int(60 * (1 - r/8))
            temp = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(temp)
            tdraw.ellipse([nx-r, ny-r, nx+r, ny+r], fill=GOLD + (alpha,))
            img = Image.alpha_composite(img.convert('RGBA'), temp).convert('RGB')
        draw.ellipse([nx-3, ny-3, nx+3, ny+3], fill=GOLD)

    # ── Constellation-like connection lines ──
    for i in range(len(node_angles)):
        for j in range(i+1, len(node_angles)):
            rad_i = math.radians(node_angles[i])
            rad_j = math.radians(node_angles[j])
            x1 = cx + ring_rx * math.cos(rad_i)
            y1 = cy + ring_ry * math.sin(rad_i) - int(h * 0.06)
            x2 = cx + ring_rx * math.cos(rad_j)
            y2 = cy + ring_ry * math.sin(rad_j) - int(h * 0.06)
            # Dashed line effect
            dx, dy = x2 - x1, y2 - y1
            dist = math.sqrt(dx**2 + dy**2)
            steps = int(dist / 6)
            for k in range(steps):
                if k % 3 == 0:
                    t = k / steps
                    px = x1 + dx * t
                    py = y1 + dy * t
                    draw.ellipse([px-2, py-2, px+2, py+2], fill=(60, 80, 120))

    return img


def create_highlights_bg():
    """Core highlights slide background - subtle orbital layout."""
    img = create_starfield_bg(seed=77)
    draw = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2

    # ── Five orbital node positions (pentagon-like) ──
    positions = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)  # Start from top
        rx = int(w * 0.32)
        ry = int(h * 0.28)
        x = cx + rx * math.cos(angle)
        y = cy + ry * math.sin(angle) - int(h * 0.02)
        positions.append((x, y))

    # ── Faint orbit ring ──
    for angle in range(0, 360, 3):
        rad = math.radians(angle)
        x = cx + int(w * 0.32) * math.cos(rad)
        y = cy + int(h * 0.28) * math.sin(rad) - int(h * 0.02)
        bright = 15 + int(10 * abs(math.sin(rad * 2.5)))
        draw.point((int(x), int(y)), fill=(bright+15, bright+15, bright+30))

    # ── Constellation lines ──
    for i in range(5):
        for j in range(i+1, 5):
            x1, y1 = positions[i]
            x2, y2 = positions[j]
            dx, dy = x2 - x1, y2 - y1
            dist = math.sqrt(dx**2 + dy**2)
            steps = int(dist / 8)
            for k in range(steps):
                if k % 4 < 2:
                    t = k / steps
                    px = x1 + dx * t
                    py = y1 + dy * t
                    draw.ellipse([px-1, py-1, px+1, py+1], fill=(35, 45, 70))

    # ── Faint node glows at positions ──
    for x, y in positions:
        for r in range(15, 0, -3):
            alpha = int(15 * (1 - r/15))
            temp = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(temp)
            tdraw.ellipse([x-r, y-r, x+r, y+r], fill=GOLD + (alpha,))
            img = Image.alpha_composite(img.convert('RGBA'), temp).convert('RGB')

    return img


def create_arch_bg():
    """Architecture slide background - vertical structure feel."""
    img = create_starfield_bg(seed=123)
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # ── Subtle vertical alignment lines ──
    cx = w // 2

    # Two faint vertical columns
    for lx in [cx - 250, cx + 250]:
        for y in range(80, h - 80, 4):
            bright = 15 + int(10 * abs(math.sin(y * 0.01)))
            for px in range(-3, 4):
                xi = lx + px
                if 0 <= xi < w:
                    draw.point((xi, y), fill=(bright+10, bright+10, bright+25))

    # ── Horizontal connection bands ──
    layer_ys = [h * 0.16, h * 0.32, h * 0.48, h * 0.64, h * 0.80]
    for ly in layer_ys:
        y = int(ly)
        for x in range(int(cx - 300), int(cx + 300), 3):
            bright = 20 + int(10 * abs(math.sin(x * 0.02)))
            draw.point((x, y), fill=(bright+10, bright+10, bright+30))

    return img


# ═══════════════════════════════════════════════════════════════
# PART 2: Animation Helpers
# ═══════════════════════════════════════════════════════════════

class AnimBuilder:
    """Builds animation timing tree for a slide."""

    def __init__(self, slide):
        self.slide = slide
        self.sld = slide._element
        self._id_counter = 100
        self._ensure_anim_tree()

    def _next_id(self):
        self._id_counter += 1
        return self._id_counter

    def _ensure_anim_tree(self):
        """Create the root timing structure if missing."""
        timing = self.sld.find(qn('p:timing'))
        if timing is not None:
            self.sld.remove(timing)

        timing = etree.SubElement(self.sld, qn('p:timing'))
        tnLst = etree.SubElement(timing, qn('p:tnLst'))

        # Root par
        par = etree.SubElement(tnLst, qn('p:par'))
        cTn = etree.SubElement(par, qn('p:cTn'))
        cTn.set('id', str(self._next_id()))
        cTn.set('dur', 'indefinite')
        cTn.set('restart', 'never')
        cTn.set('nodeType', 'tmRoot')

        childTnLst = etree.SubElement(cTn, qn('p:childTnLst'))

        # Main sequence
        seq = etree.SubElement(childTnLst, qn('p:seq'))
        seq.set('concurrent', '1')
        seq.set('nextAc', 'seek')

        seq_cTn = etree.SubElement(seq, qn('p:cTn'))
        seq_cTn.set('id', str(self._next_id()))
        seq_cTn.set('dur', 'indefinite')
        seq_cTn.set('nodeType', 'mainSeq')

        self._seq_child_lst = etree.SubElement(seq_cTn, qn('p:childTnLst'))

    def add_fade(self, shape, delay=0, duration=800):
        """Add a fade-in entrance animation to a shape (after previous)."""
        spid = shape.shape_id
        par = etree.SubElement(self._seq_child_lst, qn('p:par'))

        cTn = etree.SubElement(par, qn('p:cTn'))
        cTn.set('id', str(self._next_id()))
        cTn.set('dur', str(duration))
        cTn.set('fill', 'hold')

        child = etree.SubElement(cTn, qn('p:childTnLst'))

        anim = etree.SubElement(child, qn('p:animEffect'))
        anim.set('transition', 'in')
        anim.set('filter', 'fade')

        anim_cTn = etree.SubElement(anim, qn('p:cTn'))
        anim_cTn.set('id', str(self._next_id()))
        anim_cTn.set('dur', str(duration))

        tgt = etree.SubElement(anim, qn('p:tgtEl'))
        spTgt = etree.SubElement(tgt, qn('p:spTgt'))
        spTgt.set('spid', str(spid))

    def add_fade_with_prev(self, shape, duration=800):
        """Add a fade-in that starts with the previous animation."""
        spid = shape.shape_id
        # Find the last par and add to its child list
        pars = self._seq_child_lst.findall(qn('p:par'))
        if not pars:
            self.add_fade(shape, 0, duration)
            return
        last_par = pars[-1]
        last_cTn = last_par.find(qn('p:cTn'))
        last_child = last_cTn.find(qn('p:childTnLst'))

        anim = etree.SubElement(last_child, qn('p:animEffect'))
        anim.set('transition', 'in')
        anim.set('filter', 'fade')

        anim_cTn = etree.SubElement(anim, qn('p:cTn'))
        anim_cTn.set('id', str(self._next_id()))
        anim_cTn.set('dur', str(duration))

        tgt = etree.SubElement(anim, qn('p:tgtEl'))
        spTgt = etree.SubElement(tgt, qn('p:spTgt'))
        spTgt.set('spid', str(spid))


def add_slide_transition(slide, trans_type='fade', duration=500):
    """Add slide transition."""
    sld = slide._element
    trans = etree.SubElement(sld, qn('p:transition'))
    trans.set('advTm', str(duration))
    if trans_type == 'fade':
        fade = etree.SubElement(trans, qn('p:fade'))
        fade.set('thruBlk', '0')
    elif trans_type == 'push':
        etree.SubElement(trans, qn('p:push'))
    elif trans_type == 'cover':
        etree.SubElement(trans, qn('p:cover'))


# ═══════════════════════════════════════════════════════════════
# PART 3: PPTX Builder
# ═══════════════════════════════════════════════════════════════

def rgb(hex_str):
    """Convert hex color like '#F0C060' to RGBColor."""
    hex_str = hex_str.lstrip('#')
    return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def set_slide_bg(slide, img):
    """Set a PIL Image as the slide background."""
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Add image to slide's image part
    img_part = slide.part.get_or_add_image_part(buf)

    # Create background XML
    bg = slide._element.find(qn('p:cSld'))
    bgPr = etree.Element(qn('p:bgPr'))

    blipFill = etree.SubElement(bgPr, qn('p:blipFill'))
    blip = etree.SubElement(blipFill, qn('a:blip'))
    blip.set(qn('r:embed'), img_part.rel._rId)

    stretch = etree.SubElement(blipFill, qn('a:stretch'))
    fillRect = etree.SubElement(stretch, qn('a:fillRect'))

    # Set mode to tile or stretch
    blipFill.append(etree.Element(qn('a:stretch')))

    bg.insert(0, bgPr)


def set_slide_bg_image(slide, img_path):
    """Set background from image file."""
    from pptx.oxml.ns import qn as _qn
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(0x0A, 0x0E, 0x27)

    # Use XML manipulation for proper image background
    sld_bg = slide._element.find(_qn('p:cSld'))
    bgPr = etree.SubElement(sld_bg, _qn('p:bgPr'))
    blipFill = etree.SubElement(bgPr, _qn('p:blipFill'))
    blip = etree.SubElement(blipFill, _qn('a:blip'))
    blip.set(_qn('r:embed'), img_path)  # This won't work without proper rel
    stretch = etree.SubElement(blipFill, _qn('a:stretch'))
    etree.SubElement(stretch, _qn('a:fillRect'))


def add_bg_image(slide, img):
    """Set background by adding a full-slide picture from BytesIO buffer."""
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Save to temp file for add_picture (simplest reliable method)
    tmp_path = os.path.join(OUTPUT_DIR, '_temp_bg', f'bg_slide_{slide.slide_id}.png')
    img.save(tmp_path)

    # Add full-slide picture
    slide.shapes.add_picture(
        tmp_path,
        Inches(0), Inches(0),
        SLIDE_W, SLIDE_H
    )


class EiraPptBuilder:
    """Build the Eira Deep Space Orbit presentation."""

    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width = SLIDE_W
        self.prs.slide_height = SLIDE_H

        # Generate backgrounds
        print("Generating cover background...")
        self.bg_cover = create_cover_bg()
        print("Generating highlights background...")
        self.bg_highlights = create_highlights_bg()
        print("Generating architecture background...")
        self.bg_arch = create_arch_bg()

        # Save temp backgrounds
        self.bg_dir = os.path.join(OUTPUT_DIR, '_temp_bg')
        os.makedirs(self.bg_dir, exist_ok=True)
        self.bg_cover.save(os.path.join(self.bg_dir, 'bg_cover.png'))
        self.bg_highlights.save(os.path.join(self.bg_dir, 'bg_highlights.png'))
        self.bg_arch.save(os.path.join(self.bg_dir, 'bg_arch.png'))

    def add_gold_accent_line(self, slide, left, top, width, height=Pt(3)):
        """Add a gold accent line."""
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb('#F0C060')
        shape.line.fill.background()
        return shape

    def add_text_box(self, slide, left, top, width, height, text, font_size=Pt(18),
                     color='#E0E8F0', bold=False, alignment=PP_ALIGN.LEFT,
                     font_name='Arial', anchor=MSO_ANCHOR.MIDDLE):
        """Add a text box with consistent styling."""
        txBox = slide.shapes.add_textbox(left, top, width, height)
        txBox.word_wrap = True
        tf = txBox.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT

        p = tf.paragraphs[0]
        p.text = text
        p.font.size = font_size
        p.font.color.rgb = rgb(color)
        p.font.bold = bold
        p.font.name = font_name
        p.alignment = alignment

        # Set text anchor
        txBox.text_frame.paragraphs[0].font.name = font_name

        # Set vertical anchor
        bodyPr = txBox._element.find(qn('p:txBody')).find(qn('a:bodyPr'))
        if bodyPr is not None:
            if anchor == MSO_ANCHOR.MIDDLE:
                bodyPr.set('anchor', 'ctr')
            elif anchor == MSO_ANCHOR.TOP:
                bodyPr.set('anchor', 't')
            elif anchor == MSO_ANCHOR.BOTTOM:
                bodyPr.set('anchor', 'b')

        return txBox

    def build_cover_slide(self):
        """Slide 1: Cover / Title Slide."""
        slide_layout = self.prs.slide_layouts[6]  # blank layout
        slide = self.prs.slides.add_slide(slide_layout)

        # ── Background ──
        add_bg_image(slide, self.bg_cover)

        # ── Top decorative line ──
        self.add_gold_accent_line(
            slide,
            Inches(3.5), Inches(1.3), Inches(6.333), Pt(2)
        )

        # ── Title: "Eira" ──
        self.add_text_box(
            slide,
            Inches(3.5), Inches(1.55), Inches(6.333), Inches(1.8),
            "Eira",
            font_size=Pt(72),
            color='#F0C060',
            bold=True,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        # ── Subtitle ──
        self.add_text_box(
            slide,
            Inches(3.5), Inches(3.2), Inches(6.333), Inches(0.8),
            "AI数字人 景区导览系统",
            font_size=Pt(28),
            color='#80C8FF',
            bold=False,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        # ── Bottom decorative line ──
        self.add_gold_accent_line(
            slide,
            Inches(4.5), Inches(4.2), Inches(4.333), Pt(2)
        )

        # ── Tagline ──
        self.add_text_box(
            slide,
            Inches(4.0), Inches(4.5), Inches(5.333), Inches(0.6),
            "中国软件杯 · 大学生软件设计大赛",
            font_size=Pt(16),
            color='#C0D0E0',
            bold=False,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        # ── Bottom glow line ──
        self.add_text_box(
            slide,
            Inches(3.0), Inches(6.2), Inches(7.333), Inches(0.5),
            "——  深空星轨  ·  Deep Space Orbit  ——",
            font_size=Pt(12),
            color='#506080',
            bold=False,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        # ── Animations ──
        anim = AnimBuilder(slide)

        # Collect shapes that were just added
        all_shapes = list(slide.shapes)
        bg_pic = all_shapes[0]       # background
        line1 = all_shapes[1]        # gold line
        title = all_shapes[2]        # "Eira"
        subtitle = all_shapes[3]     # subtitle
        line2 = all_shapes[4]        # bottom line
        tagline = all_shapes[5]      # competition tag
        bottom = all_shapes[6]       # bottom style text

        anim.add_fade(title, delay=200, duration=1200)
        anim.add_fade_with_prev(line1, duration=800)
        anim.add_fade(subtitle, delay=400, duration=1000)
        anim.add_fade_with_prev(line2, duration=800)
        anim.add_fade_with_prev(tagline, duration=800)
        anim.add_fade(bottom, delay=200, duration=800)

        # ── Slide transition ──
        add_slide_transition(slide, 'fade', 800)

        print("  Cover slide created.")
        return slide

    def build_highlights_slide(self):
        """Slide 2: Core Highlights - 5 selling points in orbital layout."""
        slide_layout = self.prs.slide_layouts[6]
        slide = self.prs.slides.add_slide(slide_layout)

        # ── Background ──
        add_bg_image(slide, self.bg_highlights)

        # ── Section header ──
        self.add_text_box(
            slide,
            Inches(3.0), Inches(0.4), Inches(7.333), Inches(0.8),
            "核心亮点",
            font_size=Pt(36),
            color='#F0C060',
            bold=True,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        self.add_gold_accent_line(
            slide,
            Inches(5.0), Inches(1.1), Inches(3.333), Pt(2)
        )

        # ── Five highlight cards in pentagonal layout ──
        highlights = [
            {
                'icon': '◆',  # ◆
                'title': '多模态交互',
                'subtitle': 'Multimodal Interaction',
                'desc': '语音 + 文字多模态对话，支持自然语言理解',
                'color': '#F0C060',
            },
            {
                'icon': '▶',  # ▶
                'title': 'Live2D数字人',
                'subtitle': 'Live2D Avatar',
                'desc': '二次元角色实时渲染，行为表情自然流畅',
                'color': '#80C8FF',
            },
            {
                'icon': '●',  # ●
                'title': 'RAG知识库',
                'subtitle': 'RAG Knowledge',
                'desc': '景区知识检索增强生成，精准解答游客问题',
                'color': '#F0C060',
            },
            {
                'icon': '▲',  # ▲
                'title': '语音流式',
                'subtitle': 'Streaming Voice',
                'desc': 'WebSocket实时语音流，低延迟自然对话体验',
                'color': '#80C8FF',
            },
            {
                'icon': '★',  # ★
                'title': '7×24在线',
                'subtitle': 'Always Online',
                'desc': '全天候智能服务，无需人工值守降低运营成本',
                'color': '#F0C060',
            },
        ]

        # Layout: top card, then 2 left, 2 right
        positions = [
            (Inches(5.16), Inches(1.5)),    # top center
            (Inches(1.1), Inches(2.8)),     # left 1
            (Inches(1.1), Inches(4.6)),     # left 2
            (Inches(9.2), Inches(2.8)),     # right 1
            (Inches(9.2), Inches(4.6)),     # right 2
        ]

        card_w = Inches(3.1)
        card_h = Inches(1.55)

        for i, (hl, (left, top)) in enumerate(zip(highlights, positions)):
            # ── Card background (semi-transparent effect via dark rectangle) ──
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, left, top, card_w, card_h
            )
            card.fill.solid()
            card.fill.fore_color.rgb = rgb('#141830')
            card.line.color.rgb = rgb('#2A3050')
            card.line.width = Pt(1)

            # Adjust corner radius
            card.adjustments[0] = 0.1

            # Make it partially transparent via XML
            solidFill = card._element.find(qn('p:spPr')).find(qn('a:solidFill'))
            if solidFill is not None:
                srgb = solidFill.find(qn('a:srgbClr'))
                if srgb is not None:
                    alpha = etree.SubElement(srgb, qn('a:alpha'))
                    alpha.set('val', '75000')  # 75% opacity

            # ── Icon ──
            icon_left = left + Inches(0.15)
            icon_top = top + Inches(0.15)
            self.add_text_box(
                slide,
                icon_left, icon_top, Inches(0.35), Inches(0.35),
                hl['icon'],
                font_size=Pt(18),
                color=hl['color'],
                bold=True,
                alignment=PP_ALIGN.CENTER,
                font_name='Arial',
            )

            # ── Title ──
            title_left = left + Inches(0.55)
            self.add_text_box(
                slide,
                title_left, icon_top, card_w - Inches(0.7), Inches(0.35),
                hl['title'],
                font_size=Pt(15),
                color=hl['color'],
                bold=True,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Subtitle (English) ──
            self.add_text_box(
                slide,
                title_left, top + Inches(0.48), card_w - Inches(0.7), Inches(0.25),
                hl['subtitle'],
                font_size=Pt(9),
                color='#6070A0',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Description ──
            self.add_text_box(
                slide,
                left + Inches(0.2), top + Inches(0.8), card_w - Inches(0.4), Inches(0.65),
                hl['desc'],
                font_size=Pt(11),
                color='#A0B0C0',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
                anchor=MSO_ANCHOR.TOP,
            )

        # ── Central "Eira" glow text ──
        self.add_text_box(
            slide,
            Inches(5.0), Inches(5.7), Inches(3.333), Inches(0.6),
            "Eira 智能导览",
            font_size=Pt(16),
            color='#F0C060',
            bold=True,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
            anchor=MSO_ANCHOR.MIDDLE,
        )

        # ── Animations ──
        anim = AnimBuilder(slide)
        all_shapes = list(slide.shapes)

        # shape 0: background, 1: header, 2: accent line
        header = all_shapes[1]
        anim.add_fade(header, delay=100, duration=800)

        # shapes 3-27: the 5 cards (5 shapes each: bg, icon, title, subtitle, desc)
        # Animate each card's background + icon + title together
        for card_idx in range(5):
            base = 3 + card_idx * 5
            card_bg = all_shapes[base]       # card background
            card_icon = all_shapes[base + 1]  # icon
            card_title = all_shapes[base + 2]  # title
            anim.add_fade(card_bg, delay=150 * card_idx, duration=600)
            anim.add_fade_with_prev(card_icon, duration=400)
            anim.add_fade_with_prev(card_title, duration=500)

        # shape 28: footer
        footer = all_shapes[28]
        anim.add_fade(footer, delay=100, duration=800)

        # ── Slide transition ──
        add_slide_transition(slide, 'fade', 600)

        print("  Highlights slide created.")
        return slide

    def build_architecture_slide(self):
        """Slide 3: Five-layer architecture diagram."""
        slide_layout = self.prs.slide_layouts[6]
        slide = self.prs.slides.add_slide(slide_layout)

        # ── Background ──
        add_bg_image(slide, self.bg_arch)

        # ── Header ──
        self.add_text_box(
            slide,
            Inches(2.5), Inches(0.25), Inches(8.333), Inches(0.7),
            "技术架构",
            font_size=Pt(34),
            color='#F0C060',
            bold=True,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
        )

        self.add_gold_accent_line(
            slide,
            Inches(5.0), Inches(0.85), Inches(3.333), Pt(2)
        )

        # ── Five layers ──
        layers = [
            {
                'name': 'L1 接入层',
                'en': 'Access Layer',
                'desc': 'Web / WeChat Mini Program / API Gateway',
                'techs': 'Vue 3 · TypeScript · Nginx',
                'color': '#F0C060',
                'icon': '△',
            },
            {
                'name': 'L2 前端层',
                'en': 'Frontend Layer',
                'desc': 'Live2D Cubism 5  +  WebSocket Client  +  Audio Processor',
                'techs': 'PixiJS · Cubism SDK · Web Audio API',
                'color': '#80C8FF',
                'icon': '◆',
            },
            {
                'name': 'L3 应用层',
                'en': 'Application Layer',
                'desc': 'Chat Engine  +  Persona Management  +  Admin Dashboard',
                'techs': 'FastAPI · WebSocket · SQLAlchemy',
                'color': '#F0C060',
                'icon': '●',
            },
            {
                'name': 'L4 数据层',
                'en': 'Data Layer',
                'desc': 'Vector DB  +  Knowledge Graph  +  OSS File Storage',
                'techs': 'PostgreSQL · pgvector · Alibaba OSS',
                'color': '#80C8FF',
                'icon': '▲',
            },
            {
                'name': 'L5 AI服务',
                'en': 'AI Service Layer',
                'desc': 'LLM Chat  +  ASR / TTS  +  Embedding  +  RAG Pipeline',
                'techs': 'DeepSeek · Xunfei · OpenAI',
                'color': '#F0C060',
                'icon': '★',
            },
        ]

        layer_left = Inches(1.8)
        layer_w = Inches(4.8)
        layer_h = Inches(1.05)
        start_y = Inches(1.2)
        gap = Inches(0.12)

        # Right side detail area
        detail_left = Inches(7.4)
        detail_w = Inches(5.2)

        for i, layer in enumerate(layers):
            y = start_y + i * (layer_h + gap)

            # ── Layer box ──
            box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                layer_left, y, layer_w, layer_h
            )
            box.fill.solid()
            box.fill.fore_color.rgb = rgb('#0F1530')
            box.line.color.rgb = rgb(layer['color'])
            box.line.width = Pt(1.5)
            box.adjustments[0] = 0.08

            # Layer number badge
            badge = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                layer_left + Inches(0.15), y + Inches(0.15),
                Inches(0.5), Inches(0.5)
            )
            badge.fill.solid()
            badge.fill.fore_color.rgb = rgb(layer['color'])
            badge.line.fill.background()

            # Badge number
            lnum = str(i + 1)
            self.add_text_box(
                slide,
                layer_left + Inches(0.15), y + Inches(0.12),
                Inches(0.5), Inches(0.5),
                lnum,
                font_size=Pt(18),
                color='#0A0E27',
                bold=True,
                alignment=PP_ALIGN.CENTER,
                font_name='Arial',
            )

            # ── Layer name (Chinese) ──
            self.add_text_box(
                slide,
                layer_left + Inches(0.85), y + Inches(0.08),
                Inches(1.6), Inches(0.35),
                layer['name'],
                font_size=Pt(16),
                color=layer['color'],
                bold=True,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Layer name (English) ──
            self.add_text_box(
                slide,
                layer_left + Inches(2.5), y + Inches(0.1),
                Inches(2.1), Inches(0.3),
                layer['en'],
                font_size=Pt(11),
                color='#506080',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Description ──
            self.add_text_box(
                slide,
                layer_left + Inches(0.85), y + Inches(0.42),
                layer_w - Inches(1.1), Inches(0.28),
                layer['desc'],
                font_size=Pt(10),
                color='#8090B0',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Tech stack ──
            self.add_text_box(
                slide,
                layer_left + Inches(0.85), y + Inches(0.7),
                layer_w - Inches(1.1), Inches(0.25),
                layer['techs'],
                font_size=Pt(9),
                color='#5060A0',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

            # ── Connection arrow between layers ──
            if i < len(layers) - 1:
                arrow_y = y + layer_h
                arrow = slide.shapes.add_shape(
                    MSO_SHAPE.DOWN_ARROW,
                    layer_left + Inches(2.2), arrow_y,
                    Inches(0.3), gap
                )
                arrow.fill.solid()
                arrow.fill.fore_color.rgb = rgb('#303860')
                arrow.line.fill.background()

            # ── Right side: Layer detail card ──
            detail_y = y + Inches(0.1)
            detail_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                detail_left, detail_y, detail_w, layer_h - Inches(0.1)
            )
            detail_card.fill.solid()
            detail_card.fill.fore_color.rgb = rgb('#0C1228')
            detail_card.line.color.rgb = rgb('#1A2040')
            detail_card.line.width = Pt(0.5)
            detail_card.adjustments[0] = 0.1

            # Layer icon
            self.add_text_box(
                slide,
                detail_left + Inches(0.1), detail_y + Inches(0.05),
                Inches(0.3), Inches(0.3),
                layer['icon'],
                font_size=Pt(12),
                color=layer['color'],
                bold=True,
                alignment=PP_ALIGN.CENTER,
            )

            # Layer detail text
            detail_items = [
                '▸ ' + t.strip() for t in layer['desc'].split('+')
            ]
            detail_text = '  |  '.join(detail_items)
            self.add_text_box(
                slide,
                detail_left + Inches(0.45), detail_y + Inches(0.0),
                detail_w - Inches(0.6), layer_h - Inches(0.2),
                detail_text,
                font_size=Pt(9),
                color='#7080A0',
                bold=False,
                alignment=PP_ALIGN.LEFT,
                font_name='Arial',
            )

        # ── Vertical flow indicator on far right ──
        flow_left = Inches(12.8)
        for i in range(5):
            fy = start_y + i * (layer_h + gap) + layer_h / 2
            dot = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                flow_left, fy - Inches(0.06),
                Inches(0.12), Inches(0.12)
            )
            dot.fill.solid()
            dot.fill.fore_color.rgb = rgb('#F0C060')
            dot.line.fill.background()

            if i < 4:
                next_fy = start_y + (i + 1) * (layer_h + gap) + layer_h / 2
                connector = slide.shapes.add_connector(
                    MSO_CONNECTOR_TYPE.STRAIGHT,
                    flow_left + Inches(0.06), fy + Inches(0.06),
                    flow_left + Inches(0.06), next_fy - Inches(0.06)
                )
                connector.line.color.rgb = rgb('#303860')
                connector.line.width = Pt(1)

        # ── Bottom tagline ──
        self.add_text_box(
            slide,
            Inches(2.0), Inches(6.7), Inches(9.333), Inches(0.45),
            "五层架构 · 数据驱动 · 实时响应",
            font_size=Pt(14),
            color='#506080',
            bold=False,
            alignment=PP_ALIGN.CENTER,
            font_name='Arial',
        )

        # ── Animations ──
        anim = AnimBuilder(slide)
        all_shapes = list(slide.shapes)

        # Header (shape 1 after background pic)
        header = all_shapes[1]
        anim.add_fade(header, delay=100, duration=800)

        # Animate each layer: build a sequential reveal
        # Each layer block starts with: empty rect, badge circle, badge number,
        #   name_cn, name_en, desc, techs, arrow, detail_card, detail_icon, detail_text
        # We'll animate the main layer boxes and their content groups
        # Shapes 3-57 are the 5 layers (11 shapes each)
        for layer_idx in range(5):
            base_idx = 3 + layer_idx * 11
            layer_box = all_shapes[base_idx]
            badge = all_shapes[base_idx + 1]
            anim.add_fade(layer_box, delay=120 * layer_idx, duration=500)
            anim.add_fade_with_prev(badge, duration=400)

        # Footer
        footer = all_shapes[-1]
        anim.add_fade(footer, delay=100, duration=800)

        # ── Slide transition ──
        add_slide_transition(slide, 'fade', 600)

        print("  Architecture slide created.")
        return slide

    def save(self, filename='方向B-深空星轨.pptx'):
        """Save the presentation."""
        output_path = os.path.join(OUTPUT_DIR, filename)
        self.prs.save(output_path)
        print(f"\nPresentation saved to: {output_path}")
        return output_path

    def build_all(self):
        """Build all slides."""
        print("\n=== Building Eira Deep Space Orbit PPT ===\n")
        self.build_cover_slide()
        self.build_highlights_slide()
        self.build_architecture_slide()
        return self


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    builder = EiraPptBuilder()
    builder.build_all()
    builder.save()
    print("\nDone! All slides created successfully.")
