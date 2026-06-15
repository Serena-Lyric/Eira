"""
Eira 项目 PPT 样例 — 霓虹夜幕 (Neon Night) 风格 v2
使用 python-pptx + lxml 创建，包含动画效果
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
import os

# ── Constants ──────────────────────────────────────────
SLIDE_W = Inches(13.333)  # 16:9
SLIDE_H = Inches(7.5)

NEON_CYAN   = (0x00, 0xE5, 0xFF)
NEON_MAGENTA = (0xFF, 0x00, 0x80)
NEON_GREEN  = (0x00, 0xFF, 0x88)
NEON_AMBER  = (0xFF, 0xAA, 0x00)
NEON_PURPLE = (0xCC, 0x55, 0xFF)
DEEP_BG     = (0x05, 0x05, 0x0A)
DARK_PURPLE = (0x1A, 0x05, 0x2A)
GRID_LINE   = (0x0A, 0x1A, 0x2A)
WHITE       = (0xFF, 0xFF, 0xFF)
DIM_WHITE   = (0xAA, 0xBB, 0xCC)
DARK_CYAN   = (0x00, 0x3D, 0x55)
CARD_BG     = (0x08, 0x0C, 0x18)

def _rgb(c): return RGBColor(*c)

# ── Slide Patching (for animations) ─────────────────

def _ensure_timing(slide):
    """Ensure a p:timing tree exists on the slide and return (sld_elem, timing, tnLst)."""
    sld = slide._element
    # Find or create cSld
    cSld = sld.find(qn('p:cSld'))
    if cSld is None:
        raise ValueError('No cSld in slide')
    # Find existing timing
    timing = sld.find(qn('p:timing'))
    if timing is None:
        # Insert after cSld
        idx = list(sld).index(cSld)
        timing = etree.Element(qn('p:timing'))
        sld.insert(idx + 1, timing)
    # Find or create tnLst
    tnLst = timing.find(qn('p:tnLst'))
    if tnLst is None:
        tnLst = etree.SubElement(timing, qn('p:tnLst'))
    return sld, timing, tnLst


def _make_anim_effect(tag, filter_name, spid, **extra):
    """Build a single p:animEffect element. tag='p:animEffect' or 'p:anim'."""
    anim = etree.Element(qn(tag))
    anim.set('transition', 'in')
    anim.set('filter', filter_name)
    for k, v in extra.items():
        anim.set(k, v)
    cBhvr = etree.SubElement(anim, qn('p:cBhvr'))
    spTgt = etree.SubElement(cBhvr, qn('p:spTgt'))
    spTgt.set('spid', str(spid))
    return anim


def add_fade(slide, shape, delay='0', dur='500'):
    """Fade-in animation for a shape."""
    _, _, tnLst = _ensure_timing(slide)
    par = etree.SubElement(tnLst, qn('p:par'))
    cTn = etree.SubElement(par, qn('p:cTn'))
    cTn.set('fill', 'hold')
    if delay != '0':
        stCondLst = etree.SubElement(cTn, qn('p:stCondLst'))
        cond = etree.SubElement(stCondLst, qn('p:cond'))
        cond.set('delay', delay)
    child = etree.SubElement(par, qn('p:childTnLst'))
    par2 = etree.SubElement(child, qn('p:par'))
    cTn2 = etree.SubElement(par2, qn('p:cTn'))
    cTn2.set('nodeType', 'clickEffect')
    child2 = etree.SubElement(par2, qn('p:childTnLst'))
    # Fade animation
    anim = _make_anim_effect('p:animEffect', 'fade', shape.shape_id)
    # Add fade node
    fade_node = etree.SubElement(anim, qn('p:fade'))
    child2.append(anim)


def add_flyin(slide, shape, direction='bottom', delay='0', dur='500'):
    """Fly-in entrance animation."""
    _, _, tnLst = _ensure_timing(slide)
    par = etree.SubElement(tnLst, qn('p:par'))
    cTn = etree.SubElement(par, qn('p:cTn'))
    cTn.set('fill', 'hold')
    if delay != '0':
        stCondLst = etree.SubElement(cTn, qn('p:stCondLst'))
        cond = etree.SubElement(stCondLst, qn('p:cond'))
        cond.set('delay', delay)
    child = etree.SubElement(par, qn('p:childTnLst'))
    par2 = etree.SubElement(child, qn('p:par'))
    cTn2 = etree.SubElement(par2, qn('p:cTn'))
    cTn2.set('nodeType', 'clickEffect')
    child2 = etree.SubElement(par2, qn('p:childTnLst'))
    anim = _make_anim_effect('p:animEffect', 'fly', shape.shape_id)
    anim.set('direction', {'bottom': 'fromBottom', 'top': 'fromTop',
                           'left': 'fromLeft', 'right': 'fromRight'}.get(direction, 'fromBottom'))
    child2.append(anim)


def add_zoom(slide, shape, delay='0', dur='500'):
    """Zoom-in entrance animation."""
    _, _, tnLst = _ensure_timing(slide)
    par = etree.SubElement(tnLst, qn('p:par'))
    cTn = etree.SubElement(par, qn('p:cTn'))
    cTn.set('fill', 'hold')
    if delay != '0':
        stCondLst = etree.SubElement(cTn, qn('p:stCondLst'))
        cond = etree.SubElement(stCondLst, qn('p:cond'))
        cond.set('delay', delay)
    child = etree.SubElement(par, qn('p:childTnLst'))
    par2 = etree.SubElement(child, qn('p:par'))
    cTn2 = etree.SubElement(par2, qn('p:cTn'))
    cTn2.set('nodeType', 'clickEffect')
    child2 = etree.SubElement(par2, qn('p:childTnLst'))
    anim = _make_anim_effect('p:animEffect', 'zoom', shape.shape_id)
    anim.set('zoom', 'in')
    child2.append(anim)


def add_wipe(slide, shape, direction='right', delay='0', dur='800'):
    """Wipe-in entrance animation."""
    _, _, tnLst = _ensure_timing(slide)
    par = etree.SubElement(tnLst, qn('p:par'))
    cTn = etree.SubElement(par, qn('p:cTn'))
    cTn.set('fill', 'hold')
    if delay != '0':
        stCondLst = etree.SubElement(cTn, qn('p:stCondLst'))
        cond = etree.SubElement(stCondLst, qn('p:cond'))
        cond.set('delay', delay)
    child = etree.SubElement(par, qn('p:childTnLst'))
    par2 = etree.SubElement(child, qn('p:par'))
    cTn2 = etree.SubElement(par2, qn('p:cTn'))
    cTn2.set('nodeType', 'clickEffect')
    child2 = etree.SubElement(par2, qn('p:childTnLst'))
    anim = _make_anim_effect('p:animEffect', 'wipe', shape.shape_id)
    anim.set('direction', {'right': 'fromRight', 'left': 'fromLeft',
                           'top': 'fromTop', 'bottom': 'fromBottom'}.get(direction, 'fromRight'))
    child2.append(anim)


# ── Visual Helpers ──────────────────────────────────

def set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def add_rect(slide, left, top, width, height, fill_color=None,
             line_color=None, line_width=None, glow=False, glow_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.line.fill.background()
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(fill_color)
    if line_color:
        shape.line.color.rgb = _rgb(line_color)
        shape.line.fill.solid()
        if line_width:
            shape.line.width = line_width
    if glow and glow_color:
        _add_glow(shape, glow_color)
    return shape


def _add_glow(shape, glow_color, radius='80000', alpha='60000'):
    """Add outer glow to a shape via XML."""
    spPr = shape._element.find(qn('a:spPr'))
    if spPr is None:
        spPr = etree.SubElement(shape._element, qn('a:spPr'))
    for old in spPr.findall(qn('a:effectLst')):
        spPr.remove(old)
    effectLst = etree.SubElement(spPr, qn('a:effectLst'))
    gle = etree.SubElement(effectLst, qn('a:glow'))
    gle.set('rad', radius)
    gc = etree.SubElement(gle, qn('a:srgbClr'))
    gc.set('val', '{:02X}{:02X}{:02X}'.format(*glow_color))
    a = etree.SubElement(gc, qn('a:alpha'))
    a.set('val', alpha)


def add_textbox(slide, left, top, width, height, text,
                font_name='Arial', font_size=Pt(18), font_color=WHITE,
                bold=False, alignment=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                line_spacing=1.2, glow=False, glow_color=None):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    txBox.word_wrap = True
    tf = txBox.text_frame
    tf.word_wrap = True
    tf._txBody.bodyPr.set('anchor', {
        MSO_ANCHOR.TOP: 't', MSO_ANCHOR.MIDDLE: 'ctr', MSO_ANCHOR.BOTTOM: 'b'}.get(anchor, 't'))
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = font_name
    p.font.size = font_size
    p.font.color.rgb = _rgb(font_color)
    p.font.bold = bold
    p.alignment = alignment
    p.line_spacing = float(line_spacing)
    if glow and glow_color:
        r = p._p.find(qn('a:r'))
        if r is not None:
            rPr = r.find(qn('a:rPr'))
            if rPr is not None:
                for old in rPr.findall(qn('a:effectLst')):
                    rPr.remove(old)
                effLst = etree.SubElement(rPr, qn('a:effectLst'))
                gle = etree.SubElement(effLst, qn('a:glow'))
                gle.set('rad', '60000')
                gc = etree.SubElement(gle, qn('a:srgbClr'))
                gc.set('val', '{:02X}{:02X}{:02X}'.format(*glow_color))
                alpha = etree.SubElement(gc, qn('a:alpha'))
                alpha.set('val', '70000')
    return txBox


def add_line(slide, x1, y1, x2, y2, color=NEON_CYAN, width=Pt(1.5)):
    connector = slide.shapes.add_connector(1, x1, y1, x2, y2)
    connector.line.color.rgb = _rgb(color)
    connector.line.width = width
    connector.line.fill.solid()
    return connector


# ── HUD Grid ────────────────────────────────────────

def draw_hud_grid(slide):
    for y_pct in [0.15, 0.30, 0.50, 0.70, 0.85]:
        y = int(SLIDE_H * y_pct)
        add_line(slide, 0, y, SLIDE_W, y, GRID_LINE, Pt(0.3))
    for x_pct in [0.1, 0.25, 0.5, 0.75, 0.9]:
        x = int(SLIDE_W * x_pct)
        add_line(slide, x, 0, x, SLIDE_H, GRID_LINE, Pt(0.3))
    # Corner brackets
    bs, m = Inches(0.3), Inches(0.3)
    for (ox, oy, sx, sy) in [
        (m, m, 1, 1), (SLIDE_W - m, m, -1, 1),
        (m, SLIDE_H - m, 1, -1), (SLIDE_W - m, SLIDE_H - m, -1, -1)
    ]:
        add_line(slide, ox, oy + bs * sy, ox, oy, NEON_CYAN, Pt(1.5))
        add_line(slide, ox, oy, ox + bs * sx, oy, NEON_CYAN, Pt(1.5))


# ── Slide 1: Cover ──────────────────────────────────

def create_cover_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DEEP_BG)

    # Gradient "light bleed" areas
    r1 = add_rect(slide, Inches(0), Inches(0), Inches(5.5), Inches(5),
                  fill_color=DARK_PURPLE, glow=True, glow_color=DARK_PURPLE)
    r2 = add_rect(slide, Inches(8.5), Inches(3.5), Inches(4.8), Inches(4),
                  fill_color=DARK_CYAN, glow=True, glow_color=DARK_CYAN)

    draw_hud_grid(slide)

    # Neon accent lines
    l_top = add_line(slide, Inches(0.8), Inches(1.8), Inches(12.5), Inches(1.8), NEON_CYAN, Pt(1.5))
    l_bot = add_line(slide, Inches(0.8), Inches(5.7), Inches(12.5), Inches(5.7), NEON_MAGENTA, Pt(1.5))
    l_lft = add_line(slide, Inches(1.2), Inches(1.8), Inches(1.2), Inches(5.7), NEON_CYAN, Pt(1))

    # Center diamond accent
    cx, cy, sz = Inches(6.6), Inches(3.75), Inches(0.2)
    diamond = slide.shapes.add_shape(MSO_SHAPE.DIAMOND, cx - sz/2, cy - sz/2, sz, sz)
    diamond.fill.solid()
    diamond.fill.fore_color.rgb = _rgb(NEON_CYAN)
    diamond.line.fill.background()
    _add_glow(diamond, NEON_CYAN, '120000', '80000')

    # Title
    t_title = add_textbox(slide, Inches(1.5), Inches(2.1), Inches(10), Inches(1.2),
                          'Eira', font_name='Arial', font_size=Pt(84),
                          font_color=NEON_CYAN, bold=True,
                          alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
                          glow=True, glow_color=NEON_CYAN)

    # Subtitle
    t_sub = add_textbox(slide, Inches(1.5), Inches(3.3), Inches(10), Inches(0.5),
                        'AI  数字人景区导览系统',
                        font_name='Arial', font_size=Pt(26),
                        font_color=NEON_MAGENTA, bold=True,
                        alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
                        glow=True, glow_color=NEON_MAGENTA)

    # Tagline
    t_tag = add_textbox(slide, Inches(1.5), Inches(4.05), Inches(10), Inches(0.45),
                        'Live2D  x  多模态交互  x  RAG知识引擎',
                        font_name='Courier New', font_size=Pt(14),
                        font_color=DIM_WHITE, bold=False,
                        alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # Bottom info line
    t_info = add_textbox(slide, Inches(1.5), Inches(6.3), Inches(10), Inches(0.35),
                         '"中国软件杯" 大学生软件设计大赛   2026',
                         font_name='Courier New', font_size=Pt(11),
                         font_color=DIM_WHITE, bold=False,
                         alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # Scan line decoration (horizontal stripes)
    for i in range(6):
        y = Inches(6.55) + Inches(i * 0.05)
        add_line(slide, Inches(4.2), y, Inches(9.1), y,
                 NEON_CYAN if i % 2 == 0 else (0x00, 0x50, 0x70), Pt(0.5))

    # Bottom glow bar
    bar_bot = add_rect(slide, Inches(4.5), Inches(6.85), Inches(4.3), Inches(0.025),
                       fill_color=NEON_CYAN, glow=True, glow_color=NEON_CYAN)

    # ── Animations for Cover ──
    add_fade(slide, t_title, dur='800')
    add_flyin(slide, t_sub, direction='bottom', delay='300', dur='600')
    add_wipe(slide, l_top, direction='right', dur='1000')
    add_wipe(slide, l_bot, direction='left', dur='1000')
    add_fade(slide, t_tag, delay='500', dur='600')
    add_fade(slide, t_info, delay='800', dur='500')
    add_fade(slide, diamond, delay='200', dur='600')
    add_wipe(slide, bar_bot, direction='right', delay='600', dur='800')

    return slide


# ── Slide 2: Core Highlights ────────────────────────

def create_highlights_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DEEP_BG)

    # Gradient bleed
    add_rect(slide, Inches(0), Inches(0), Inches(3), Inches(7.5), fill_color=DARK_PURPLE)
    add_rect(slide, Inches(10.5), Inches(4.5), Inches(2.8), Inches(3), fill_color=DARK_CYAN)

    draw_hud_grid(slide)

    # Section header
    t_sec = add_textbox(slide, Inches(0.8), Inches(0.25), Inches(5), Inches(0.5),
                        '// CORE FEATURES',
                        font_name='Courier New', font_size=Pt(13),
                        font_color=NEON_CYAN, bold=True,
                        anchor=MSO_ANCHOR.MIDDLE, glow=True, glow_color=NEON_CYAN)

    t_main = add_textbox(slide, Inches(0.8), Inches(0.6), Inches(11.5), Inches(0.75),
                         '核 心 亮 点',
                         font_name='Arial', font_size=Pt(38),
                         font_color=WHITE, bold=True,
                         anchor=MSO_ANCHOR.MIDDLE)

    bar_t = add_rect(slide, Inches(0.8), Inches(1.35), Inches(2.2), Inches(0.03),
                     fill_color=NEON_CYAN, glow=True, glow_color=NEON_CYAN)
    add_line(slide, Inches(0.8), Inches(1.55), Inches(12.5), Inches(1.55), NEON_CYAN, Pt(0.5))

    # Feature cards
    features = [
        {'id': '01', 't1': '多模态', 't2': '交互', 'sub': 'Multimodal',
         'desc': '文字 · 语音 · 视觉\n无缝切换自然对话',
         'color': NEON_CYAN},
        {'id': '02', 't1': 'Live2D', 't2': '数字人', 'sub': 'Avatar',
         'desc': '二次元角色实时渲染\n表情 / 动作 / 口型同步',
         'color': NEON_MAGENTA},
        {'id': '03', 't1': 'RAG', 't2': '知识库', 'sub': 'Knowledge',
         'desc': '景区知识增强检索\n精准回答率 95%+',
         'color': NEON_GREEN},
        {'id': '04', 't1': '语音', 't2': '流式', 'sub': 'Streaming',
         'desc': 'ASR → LLM → TTS\n全链路流式低延迟',
         'color': NEON_AMBER},
        {'id': '05', 't1': '7×24', 't2': '在线', 'sub': 'Always On',
         'desc': '全天候智能服务\n零等待即时响应',
         'color': NEON_CYAN},
    ]

    card_w = Inches(2.2)
    card_h = Inches(5.0)
    start_x = Inches(0.75)
    gap = Inches(0.28)
    card_y = Inches(1.85)

    card_shapes = []

    for i, feat in enumerate(features):
        x = start_x + i * (card_w + gap)
        lc = feat['color']

        # Card background
        card = add_rect(slide, x, card_y, card_w, card_h, fill_color=CARD_BG,
                        line_color=lc, line_width=Pt(0.8), glow=True, glow_color=lc)

        # Corner brackets
        b = Inches(0.08)
        for (cx1, cy1, dx, dy) in [
            (0, 0, 1, 0), (0, 0, 0, 1),
            (card_w, 0, -1, 0), (card_w, 0, 0, 1),
            (0, card_h, 1, 0), (0, card_h, 0, -1),
            (card_w, card_h, -1, 0), (card_w, card_h, 0, -1),
        ]:
            bx = x + cx1
            by = card_y + cy1
            add_line(slide, bx, by + b * dy, bx, by, lc, Pt(1))
            add_line(slide, bx, by, bx + b * dx, by, lc, Pt(1))

        # ID number
        add_textbox(slide, x + Inches(0.15), card_y + Inches(0.15),
                    Inches(0.8), Inches(0.45),
                    feat['id'], font_name='Courier New', font_size=Pt(20),
                    font_color=lc, bold=True, glow=True, glow_color=lc)

        # Title line 1
        add_textbox(slide, x + Inches(0.15), card_y + Inches(0.75),
                    Inches(1.9), Inches(0.5),
                    feat['t1'], font_name='Arial', font_size=Pt(20),
                    font_color=WHITE, bold=True)
        # Title line 2
        t_t2 = add_textbox(slide, x + Inches(0.15), card_y + Inches(1.15),
                           Inches(1.9), Inches(0.45),
                           feat['t2'], font_name='Arial', font_size=Pt(20),
                           font_color=WHITE, bold=True)

        # Subtitle
        add_textbox(slide, x + Inches(0.15), card_y + Inches(1.7),
                    Inches(1.9), Inches(0.3),
                    feat['sub'], font_name='Courier New', font_size=Pt(9),
                    font_color=DIM_WHITE)

        # Divider
        add_line(slide, x + Inches(0.15), card_y + Inches(2.2),
                 x + card_w - Inches(0.3), card_y + Inches(2.2), lc, Pt(0.5))

        # Description
        add_textbox(slide, x + Inches(0.15), card_y + Inches(2.5),
                    Inches(1.9), Inches(2.0),
                    feat['desc'], font_name='Courier New', font_size=Pt(10),
                    font_color=DIM_WHITE, line_spacing=1.6)

        card_shapes.append(card)

    # Animations for highlights
    add_fade(slide, t_sec, dur='400')
    add_fade(slide, t_main, delay='100', dur='500')
    add_wipe(slide, bar_t, direction='right', delay='200', dur='600')
    for idx, card in enumerate(card_shapes):
        add_flyin(slide, card, direction='bottom', delay=str(300 + idx * 150), dur='500')

    return slide


# ── Slide 3: Technical Architecture ─────────────────

def create_architecture_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DEEP_BG)

    add_rect(slide, Inches(11), Inches(0), Inches(2.3), Inches(3.5), fill_color=DARK_PURPLE)
    add_rect(slide, Inches(0), Inches(5.5), Inches(4), Inches(2), fill_color=DARK_CYAN)

    draw_hud_grid(slide)

    # Section header
    t_sec = add_textbox(slide, Inches(0.8), Inches(0.25), Inches(5), Inches(0.5),
                        '// ARCHITECTURE',
                        font_name='Courier New', font_size=Pt(13),
                        font_color=NEON_MAGENTA, bold=True,
                        anchor=MSO_ANCHOR.MIDDLE, glow=True, glow_color=NEON_MAGENTA)

    t_main = add_textbox(slide, Inches(0.8), Inches(0.6), Inches(11.5), Inches(0.75),
                         '技 术 架 构',
                         font_name='Arial', font_size=Pt(38),
                         font_color=WHITE, bold=True,
                         anchor=MSO_ANCHOR.MIDDLE)

    bar_t = add_rect(slide, Inches(0.8), Inches(1.35), Inches(2.2), Inches(0.03),
                     fill_color=NEON_MAGENTA, glow=True, glow_color=NEON_MAGENTA)
    add_line(slide, Inches(0.8), Inches(1.55), Inches(12.5), Inches(1.55), NEON_MAGENTA, Pt(0.5))

    # Layer definitions
    layers = [
        {'lvl': 'L1', 'cn': '接入层', 'en': 'Access Layer',
         'items': 'WebSocket · REST API · OAuth2 · 负载均衡',
         'color': NEON_CYAN, 'icon': '◈'},
        {'lvl': 'L2', 'cn': '前端层', 'en': 'Frontend',
         'items': 'Vue 3 · Live2D Cubism 5 · Web Audio API · WaveSurfer',
         'color': NEON_GREEN, 'icon': '◈'},
        {'lvl': 'L3', 'cn': '应用层', 'en': 'Application',
         'items': 'FastAPI · LangChain · Multi-Agent · 流式管道',
         'color': NEON_MAGENTA, 'icon': '◈'},
        {'lvl': 'L4', 'cn': '数据层', 'en': 'Data Layer',
         'items': 'PostgreSQL + pgvector · Redis · 阿里云 OSS · Elasticsearch',
         'color': NEON_AMBER, 'icon': '◈'},
        {'lvl': 'L5', 'cn': 'AI 服务', 'en': 'AI Services',
         'items': 'LLM · ASR · TTS · Embedding · Reranker',
         'color': NEON_PURPLE, 'icon': '◈'},
    ]

    layer_h = Inches(0.85)
    layer_w = Inches(10.2)
    layer_x = Inches(1.5)
    start_y = Inches(2.0)
    layer_gap = Inches(0.18)

    layer_shapes = []

    for i, layer in enumerate(layers):
        y = start_y + i * (layer_h + layer_gap)
        lc = layer['color']

        # Layer backdrop
        card = add_rect(slide, layer_x, y, layer_w, layer_h, fill_color=CARD_BG,
                        line_color=lc, line_width=Pt(0.8), glow=True, glow_color=lc)
        layer_shapes.append(card)

        # Level badge
        badge = add_rect(slide, layer_x + Inches(0.1), y + Inches(0.1),
                         Inches(0.75), Inches(0.65),
                         fill_color=(0x0A, 0x14, 0x22),
                         line_color=lc, line_width=Pt(1.2))

        add_textbox(slide, layer_x + Inches(0.1), y + Inches(0.1),
                    Inches(0.75), Inches(0.65),
                    layer['lvl'], font_name='Courier New', font_size=Pt(22),
                    font_color=lc, bold=True,
                    alignment=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
                    glow=True, glow_color=lc)

        # Chinese name
        add_textbox(slide, layer_x + Inches(1.15), y + Inches(0.08),
                    Inches(2), Inches(0.4),
                    layer['cn'], font_name='Arial', font_size=Pt(18),
                    font_color=WHITE, bold=True,
                    anchor=MSO_ANCHOR.MIDDLE)

        # English name
        add_textbox(slide, layer_x + Inches(1.15), y + Inches(0.48),
                    Inches(2), Inches(0.3),
                    layer['en'], font_name='Courier New', font_size=Pt(9),
                    font_color=DIM_WHITE,
                    anchor=MSO_ANCHOR.MIDDLE)

        # Items list
        add_textbox(slide, layer_x + Inches(3.3), y + Inches(0.1),
                    Inches(5.5), Inches(0.65),
                    layer['items'], font_name='Courier New', font_size=Pt(11),
                    font_color=lc, bold=False,
                    anchor=MSO_ANCHOR.MIDDLE)

        # Downward connector between layers
        if i < len(layers) - 1:
            nlc = layers[i + 1]['color']
            ax = layer_x + layer_w / 2
            ay = y + layer_h
            conn = slide.shapes.add_shape(
                MSO_SHAPE.ISOSCELES_TRIANGLE,
                ax - Inches(0.06), ay + Inches(0.02),
                Inches(0.12), Inches(0.12))
            conn.fill.solid()
            conn.fill.fore_color.rgb = _rgb(lc)
            conn.line.fill.background()
            conn.rotation = 180.0
            _add_glow(conn, lc, '30000', '50000')

    # Right-side annotations
    ann_x = Inches(11.9)
    annotations = [
        ('WebSocket 全双工', NEON_CYAN),
        ('实时语音流', DIM_WHITE),
        ('Live2D Cubism 5', NEON_GREEN),
        ('角色渲染引擎', DIM_WHITE),
        ('LangChain Agent', NEON_MAGENTA),
        ('智能任务调度', DIM_WHITE),
        ('pgvector 语义检索', NEON_AMBER),
        ('高性能向量索引', DIM_WHITE),
        ('模型编排管线', NEON_PURPLE),
        ('多模型统一调度', DIM_WHITE),
    ]
    for j, (text, color) in enumerate(annotations):
        ann_y = Inches(2.15) + Inches(j * 0.35)
        add_textbox(slide, ann_x, ann_y, Inches(1.8), Inches(0.3),
                    text, font_name='Courier New', font_size=Pt(8),
                    font_color=color, bold=(color != DIM_WHITE),
                    anchor=MSO_ANCHOR.MIDDLE)

    # Subtitle describing data flow
    add_textbox(slide, Inches(1.5), Inches(6.5), Inches(10), Inches(0.35),
                '↑ 数据上行: 用户输入 → ASR → NLU → Agent → RAG → LLM → TTS → 前端渲染',
                font_name='Courier New', font_size=Pt(9),
                font_color=DIM_WHITE, alignment=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE)

    # Animations
    add_fade(slide, t_sec, dur='400')
    add_fade(slide, t_main, delay='100', dur='500')
    add_wipe(slide, bar_t, direction='right', delay='200', dur='600')
    for idx, ls in enumerate(layer_shapes):
        add_wipe(slide, ls, direction='right', delay=str(300 + idx * 180), dur='700')

    return slide


# ── Main ────────────────────────────────────────────

def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    create_cover_slide(prs)
    create_highlights_slide(prs)
    create_architecture_slide(prs)

    out = r'D:\Application\ClaudeCode\repository\Eira\docs\ppt-samples\方向A-霓虹夜幕.pptx'
    prs.save(out)
    print(f'Done: {out} ({len(prs.slides)} slides)')

if __name__ == '__main__':
    main()
