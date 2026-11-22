"""Mode cetak FOTO berwarna (kertas 4R = 4x6 inci, 300 dpi = 1200 x 1800 px).

Dipakai kalau event di Studio diset "Jenis cetak: Foto 4R". Layout sama dengan Receipt Photobooth:
  solo (1 foto), duo (2), strip (3 foto -> 2 strip 2x6 inci kembar dalam 1 lembar, tinggal dipotong), grid (4).
"""
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

import templates as T

W4R, H4R = 1200, 1800          # potret 4x6 inci @300dpi
STRIP_W = 600                   # 2x6 inci

BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]

STYLES = [
    ("warna", "Color", "True, natural color"),
    ("cerah", "Vivid", "Brighter, livelier colors"),
    ("bw", "Black & white", "Classic, soft contrast"),
    ("sepia", "Sepia", "Warm brown, old-photo look"),
    ("vintage", "Vintage", "Faded, warm, a little grain"),
    ("dingin", "Cool", "Blue tint, clean"),
]
STYLE_IDS = [s[0] for s in STYLES]


def style_photo(img, style="warna"):
    img = ImageOps.exif_transpose(img).convert("RGB")
    if style == "cerah":
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        return ImageEnhance.Brightness(img).enhance(1.05)
    if style == "bw":
        g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
        return ImageEnhance.Contrast(g).enhance(1.1).convert("RGB")
    if style == "sepia":
        g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
        return ImageOps.colorize(g, (38, 24, 12), (255, 240, 214), mid=(160, 120, 80))
    if style == "vintage":
        img = ImageEnhance.Color(img).enhance(0.7)
        img = ImageEnhance.Contrast(img).enhance(0.85)
        warm = Image.new("RGB", img.size, (255, 214, 160))
        img = Image.blend(img, warm, 0.14)
        lift = Image.new("RGB", img.size, (40, 32, 30))
        img = Image.blend(img, lift, 0.08)
        noise = Image.effect_noise(img.size, 22).convert("RGB")
        return Image.blend(img, noise, 0.05)
    if style == "dingin":
        img = ImageEnhance.Color(img).enhance(1.05)
        cool = Image.new("RGB", img.size, (170, 205, 255))
        return ImageEnhance.Brightness(Image.blend(img, cool, 0.1)).enhance(1.04)
    return img


# ---------------------------------------------------------------- helper gambar

def hexrgb(h, default=(18, 18, 18)):
    try:
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:  # noqa: BLE001
        return default


def fit(img, w, h):
    return ImageOps.fit(img, (max(1, int(w)), max(1, int(h))), Image.LANCZOS, centering=(0.5, 0.45))


def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    return m


def paste_photo(canvas, ph, box, radius=0):
    x0, y0, x1, y1 = [int(v) for v in box]
    im = fit(ph, x1 - x0, y1 - y0)
    canvas.paste(im, (x0, y0), rounded_mask(im.width, im.height, radius) if radius else None)


def shadow(canvas, box, radius=0, blur=18, off=(0, 10), alpha=70):
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = blur * 3
    sh = Image.new("L", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], radius, fill=alpha)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste((0, 0, 0), (x0 - pad + off[0], y0 - pad + off[1]), sh)


def boxes(layout, area, gap):
    x0, y0, x1, y1 = area
    w, h = x1 - x0, y1 - y0
    if layout == "solo":
        return [area]
    if layout == "duo":
        hh = (h - gap) / 2
        return [(x0, y0, x1, y0 + hh), (x0, y0 + hh + gap, x1, y1)]
    if layout == "strip":
        hh = (h - 2 * gap) / 3
        return [(x0, y0 + i * (hh + gap), x1, y0 + i * (hh + gap) + hh) for i in range(3)]
    ww, hh = (w - gap) / 2, (h - gap) / 2
    return [(x0 + c * (ww + gap), y0 + r * (hh + gap), x0 + c * (ww + gap) + ww, y0 + r * (hh + gap) + hh)
            for r in range(2) for c in range(2)]


def text_c(d, cx, y, s, f, fill, anchor="ma"):
    d.text((cx, y), s, font=f, fill=fill, anchor=anchor)


def fit_font(d, s, name, size, max_w, min_size=18):
    while size > min_size:
        f = T.F(name, size)
        if d.textlength(s, font=f) <= max_w:
            return f
        size -= 4
    return T.F(name, min_size)


class Ctx:
    def __init__(self, photos, layout, W, H, event, footer, caption, date, logo, qr, theme, lucky, number):
        self.photos, self.layout, self.W, self.H = photos, layout, W, H
        self.event, self.footer, self.caption, self.date = event, footer, caption, date
        self.logo, self.qr, self.theme, self.lucky, self.number = logo, qr, theme, lucky, number
        self.strip = layout == "strip"
        self.s = W / 1200 if not self.strip else 0.62   # skala teks

    def px(self, v):
        return int(v * self.s)

    def ph(self, i):
        return self.photos[i % len(self.photos)] if self.photos else Image.new("RGB", (400, 300), (200, 200, 200))


def put_logo(c, canvas, cx, y, max_h):
    if not c.logo:
        return y
    lg = c.logo.copy()
    lg.thumbnail((int(c.W * 0.5), max_h), Image.LANCZOS)
    canvas.paste(lg, (int(cx - lg.width / 2), int(y)), lg)
    return y + lg.height


def put_qr(c, canvas, x, y, size, fg=(18, 18, 18), bg=(255, 255, 255)):
    if not c.qr:
        return
    q = c.qr.resize((size, size), Image.NEAREST).convert("L")
    tile = Image.new("RGB", (size, size), bg)
    tile.paste(fg, (0, 0), ImageOps.invert(q))
    canvas.paste(tile, (int(x), int(y)))


def footer_block(c, canvas, top, ink, sub, name_font="serifb", accent=None):
    """Nama event, tanggal, pesan, QR di area bawah [top, H]."""
    d = ImageDraw.Draw(canvas)
    W, H = c.W, c.H
    qr_s = c.px(150) if c.qr else 0
    usable = W - 2 * c.px(60) - (2 * qr_s + c.px(40) if qr_s else 0)
    y = top
    if c.logo:
        y = put_logo(c, canvas, W / 2, y, c.px(110)) + c.px(14)
    f = fit_font(d, c.event, name_font, c.px(76), usable)
    text_c(d, W / 2, y, c.event, f, ink)
    y += f.size + c.px(16)
    if c.caption:
        f2 = fit_font(d, c.caption, "hand", c.px(56), usable)
        text_c(d, W / 2, y, c.caption, f2, accent or ink)
        y += f2.size + c.px(10)
    meta = c.date + ((f"  ·  {'DRAW' if T.get_lang() == 'en' else 'UNDIAN'} #{c.lucky}") if c.lucky else "")
    text_c(d, W / 2, y, meta, T.F("mono", c.px(26)), sub)
    if qr_s:
        put_qr(c, canvas, W - c.px(60) - qr_s, H - c.px(50) - qr_s, qr_s)


# ---------------------------------------------------------------- template

def t_klasik(c):
    bg, ink, sub = (255, 255, 255), (24, 24, 24), (120, 120, 120)
    cv = Image.new("RGB", (c.W, c.H), bg)
    m = c.px(56) if not c.strip else 36
    foot = c.px(300) if not c.strip else 330
    for i, b in enumerate(boxes(c.layout, (m, m, c.W - m, c.H - foot), m * 0.5)):
        paste_photo(cv, c.ph(i), b)
    footer_block(c, cv, c.H - foot + c.px(40), ink, sub)
    return cv


def t_gelap(c):
    bg, ink, gold = (16, 16, 18), (245, 240, 230), (201, 168, 106)
    cv = Image.new("RGB", (c.W, c.H), bg)
    d = ImageDraw.Draw(cv)
    m = c.px(60) if not c.strip else 34
    foot = c.px(320) if not c.strip else 340
    d.rectangle([m / 2, m / 2, c.W - m / 2, c.H - m / 2], outline=gold, width=2)
    for i, b in enumerate(boxes(c.layout, (m, m, c.W - m, c.H - foot), m * 0.45)):
        paste_photo(cv, c.ph(i), b)
    y = c.H - foot + c.px(46)
    d.line([c.W / 2 - c.px(90), y - c.px(16), c.W / 2 + c.px(90), y - c.px(16)], fill=gold, width=2)
    footer_block(c, cv, y, ink, gold, accent=gold)
    return cv


def t_polaroid(c):
    bg = (238, 232, 221)
    cv = Image.new("RGB", (c.W, c.H), bg)
    d = ImageDraw.Draw(cv)
    m = c.px(70) if not c.strip else 40
    foot = c.px(260) if not c.strip else 300
    import random
    rnd = random.Random(len(c.event) * 7 + len(c.photos))
    for i, b in enumerate(boxes(c.layout, (m, m, c.W - m, c.H - foot), m * 0.7)):
        x0, y0, x1, y1 = b
        bw, bh = x1 - x0, y1 - y0
        pad = max(12, int(min(bw, bh) * 0.045))
        bottom = pad * 3.2
        card = Image.new("RGBA", (int(bw), int(bh)), (252, 251, 248, 255))
        ph = fit(c.ph(i), bw - 2 * pad, bh - pad - bottom)
        card.paste(ph, (pad, pad))
        ang = 0 if c.strip else rnd.uniform(-3.5, 3.5)
        rc = card.rotate(ang, expand=True, resample=Image.BICUBIC)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        px, py = int(cx - rc.width / 2), int(cy - rc.height / 2)
        shadow(cv, (px + 8, py + 8, px + rc.width - 8, py + rc.height - 8), blur=14, alpha=60)
        cv.paste(rc, (px, py), rc)
    footer_block(c, cv, c.H - foot + c.px(30), (40, 34, 30), (130, 118, 104), name_font="hand",
                 accent=(170, 70, 50))
    return cv


def t_film(c):
    bg, orange = (14, 14, 14), (255, 156, 40)
    cv = Image.new("RGB", (c.W, c.H), bg)
    d = ImageDraw.Draw(cv)
    side = c.px(90) if not c.strip else 64
    hole_w, hole_h, step = side * 0.42, side * 0.3, side * 0.62
    y = side * 0.3
    while y < c.H - hole_h:
        for x in (side * 0.29, c.W - side * 0.29 - hole_w):
            d.rounded_rectangle([x, y, x + hole_w, y + hole_h], 5, fill=(236, 230, 214))
        y += step
    foot = c.px(250) if not c.strip else 280
    m = c.px(40) if not c.strip else 24
    for i, b in enumerate(boxes(c.layout, (side, m, c.W - side, c.H - foot), m)):
        paste_photo(cv, c.ph(i), b)
        d.text((b[0] + 6, b[3] + 2), f"{i + 1}A  >>", font=T.F("monob", max(16, c.px(22))), fill=orange)
    ty = c.H - foot + c.px(50)
    f = fit_font(d, c.event.upper(), "bebas", c.px(100), c.W - 2 * side - c.px(40))
    text_c(d, c.W / 2, ty, c.event.upper(), f, (240, 236, 226))
    ty += f.size + c.px(10)
    meta = (c.caption + "  ·  " if c.caption else "") + c.date + (f"  ·  #{c.lucky}" if c.lucky else "")
    text_c(d, c.W / 2, ty, meta, fit_font(d, meta, "mono", c.px(28), c.W - 2 * side), orange)
    if c.qr:
        s = c.px(120)
        put_qr(c, cv, c.W - side - s, c.H - s - c.px(30), s)
    return cv


def t_tema(c):
    th = c.theme or {}
    paper, ink = hexrgb(th.get("paper", "#F2EFE8")), hexrgb(th.get("text", "#121212"))
    accent, btn = hexrgb(th.get("accent", "#C8410F")), hexrgb(th.get("btn", "#121212"))
    cv = Image.new("RGB", (c.W, c.H), paper)
    d = ImageDraw.Draw(cv)
    m = c.px(56) if not c.strip else 34
    head = c.px(170) if not c.strip else 150
    foot = c.px(210) if not c.strip else 230
    d.rectangle([0, 0, c.W, head], fill=btn)
    f = fit_font(d, c.event, "serifb", c.px(80), c.W - 2 * m)
    text_c(d, c.W / 2, head / 2, c.event, f, paper, anchor="mm")
    for i, b in enumerate(boxes(c.layout, (m, head + m, c.W - m, c.H - foot), m * 0.5)):
        paste_photo(cv, c.ph(i), b, radius=c.px(26) if not c.strip else 14)
    y = c.H - foot + c.px(40)
    if c.caption:
        f2 = fit_font(d, c.caption, "hand", c.px(60), c.W - 2 * m - c.px(200))
        text_c(d, c.W / 2, y, c.caption, f2, accent)
        y += f2.size + c.px(10)
    text_c(d, c.W / 2, y, c.date + ((f" · {'DRAW' if T.get_lang() == 'en' else 'UNDIAN'} #{c.lucky}") if c.lucky else ""), T.F("mono", c.px(26)), ink)
    d.rectangle([0, c.H - c.px(18), c.W, c.H], fill=accent)
    if c.qr:
        s = c.px(140)
        put_qr(c, cv, c.W - m - s, c.H - c.px(36) - s, s, fg=ink, bg=paper)
    return cv


def t_majalah(c):
    cv = Image.new("RGB", (c.W, c.H), (20, 20, 20))
    paste_photo(cv, c.ph(0), (0, 0, c.W, c.H))
    # gradasi gelap atas & bawah supaya teks terbaca
    grad = Image.new("L", (1, 256))
    for i in range(256):
        grad.putpixel((0, i), int(max(0, 1 - i / 90) * 150 + max(0, (i - 150) / 106) * 210))
    cv.paste((0, 0, 0), (0, 0), grad.resize((c.W, c.H)))
    d = ImageDraw.Draw(cv)
    m = c.px(56) if not c.strip else 30
    mast = "PHOTOBOOTH" if not c.strip else "BOOTH"
    f = fit_font(d, mast, "bebas", c.px(250), c.W - 2 * m)
    text_c(d, c.W / 2, m * 0.6, mast, f, (255, 255, 255))
    y = m * 0.6 + f.size * 0.92
    text_c(d, c.W / 2, y, T.tr(f"EDISI SPESIAL · {c.date.upper()}"), T.F("monob", c.px(26)), (255, 214, 0))
    # foto kecil (sisa foto) di kanan bawah
    rest = c.photos[1:] if len(c.photos) > 1 else []
    if rest:
        n = len(rest)
        sw = c.px(250) if not c.strip else 150
        sh = int(sw * 0.75)
        gap = c.px(18)
        for i, ph in enumerate(rest):
            x = c.W - m - sw
            yy = c.H - c.px(330) - (n - i) * (sh + gap) if not c.strip else c.H - 420 - (n - i) * (sh + 12)
            d.rectangle([x - 6, yy - 6, x + sw + 6, yy + sh + 6], fill=(255, 255, 255))
            paste_photo(cv, ph, (x, yy, x + sw, yy + sh))
    by = c.H - (c.px(300) if not c.strip else 360)
    f2 = fit_font(d, c.event.upper(), "black", c.px(84), c.W - 2 * m)
    d.text((m, by), c.event.upper(), font=f2, fill=(255, 255, 255))
    by += f2.size + c.px(14)
    line = c.caption or T.tr("Tampil memukau malam ini")
    d.text((m, by), line, font=fit_font(d, line, "serifb", c.px(48), c.W - 2 * m - c.px(170)), fill=(255, 214, 0))
    by += c.px(64)
    d.text((m, by), T.tr("SENYUM 100% · GAYA MAKSIMAL") + (f" · #{c.lucky}" if c.lucky else ""),
           font=T.F("monob", c.px(24)), fill=(255, 255, 255))
    if c.qr:
        s = c.px(140)
        put_qr(c, cv, c.W - m - s, c.H - m - s, s)
    return cv


def t_wedding(c):
    bg, gold, ink = (250, 246, 238), (184, 150, 92), (60, 50, 42)
    cv = Image.new("RGB", (c.W, c.H), bg)
    d = ImageDraw.Draw(cv)
    m = c.px(70) if not c.strip else 40
    d.rectangle([m * 0.4, m * 0.4, c.W - m * 0.4, c.H - m * 0.4], outline=gold, width=3)
    d.rectangle([m * 0.55, m * 0.55, c.W - m * 0.55, c.H - m * 0.55], outline=gold, width=1)
    foot = c.px(330) if not c.strip else 360
    for i, b in enumerate(boxes(c.layout, (m, m, c.W - m, c.H - foot), m * 0.4)):
        x0, y0, x1, y1 = [int(v) for v in b]
        paste_photo(cv, c.ph(i), (x0, y0, x1, y1))
        d.rectangle([x0 - 1, y0 - 1, x1, y1], outline=gold, width=2)
    y = c.H - foot + c.px(40)
    if c.logo:
        y = put_logo(c, cv, c.W / 2, y, c.px(90)) + c.px(8)
    f = fit_font(d, c.event, "hand", c.px(110), c.W - 2 * m - (c.px(320) if c.qr else 0))
    text_c(d, c.W / 2, y, c.event, f, ink)
    y += f.size + c.px(6)
    cx = c.W / 2
    d.line([cx - c.px(150), y + c.px(14), cx - c.px(30), y + c.px(14)], fill=gold, width=2)
    d.line([cx + c.px(30), y + c.px(14), cx + c.px(150), y + c.px(14)], fill=gold, width=2)
    d.regular_polygon((cx, y + c.px(14), c.px(9)), 4, fill=gold)
    y += c.px(40)
    meta = (c.caption + " · " if c.caption else "") + c.date
    text_c(d, cx, y, meta, fit_font(d, meta, "serif", c.px(34), c.W - 2 * m - (c.px(320) if c.qr else 0)), gold)
    if c.qr:
        s = c.px(140)
        put_qr(c, cv, c.W - m - s, c.H - m - s, s, fg=ink, bg=bg)
    return cv


def t_bingkai(c, frame_path=None):
    """Bingkai PNG sendiri (area transparan = tempat foto). Tanpa file: pakai Klasik."""
    if not frame_path or not os.path.exists(frame_path):
        return t_klasik(c)
    fr = Image.open(frame_path).convert("RGBA")
    fr = fr.resize((c.W, c.H), Image.LANCZOS)
    slots = T.detect_slots(fr.split()[3])
    cv = Image.new("RGB", (c.W, c.H), (255, 255, 255))
    for i, b in enumerate(slots):
        paste_photo(cv, c.ph(i), b)
    cv.paste(fr, (0, 0), fr)
    if c.qr:
        s = c.px(130)
        put_qr(c, cv, c.W - c.px(40) - s, c.H - c.px(40) - s, s)
    return cv


TEMPLATES = [
    ("klasik", "Classic white", t_klasik),
    ("gelap", "Elegant black", t_gelap),
    ("polaroid", "Polaroid", t_polaroid),
    ("film", "Film roll", t_film),
    ("tema", "Event colors", t_tema),
    ("majalah", "Magazine cover", t_majalah),
    ("wedding", "Wedding", t_wedding),
    ("bingkai", "Custom frame (PNG)", t_bingkai),
]
BY_ID = {t[0]: t for t in TEMPLATES}


def date_str(now=None):
    n = now or datetime.now()
    return f"{n.day} {T.month_name(n.month)} {n.year}"


def compose_photo(photos, layout="strip", style="warna", caption="", show_logo=True, event_name="",
                  logo_path=None, qr_url=None, template="klasik", theme=None, lucky=None, number=None,
                  frames=None, asset_dir=None, footer="", now=None, brightness=1.0):
    """Hasil: RGB 1200x1800 (4R potret, 300 dpi). Strip = 2 strip kembar berdampingan."""
    styled = []
    for p in photos:
        im = style_photo(p, style)
        if brightness != 1.0:
            im = ImageEnhance.Brightness(im).enhance(brightness)
        styled.append(im)
    logo = None
    if show_logo and logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
        except Exception:  # noqa: BLE001
            logo = None
    qr = None
    if qr_url:
        from imaging import make_qr_with_logo
        qr = make_qr_with_logo(qr_url, logo=logo, as_rgb=True)
    W = STRIP_W if layout == "strip" else W4R
    c = Ctx(styled, layout, W, H4R, event_name or T.tr("NAMA EVENT"), T.tr(footer), caption or "", date_str(now), logo, qr,
            theme or {}, lucky, number)
    tid = template if template in BY_ID else "klasik"
    if tid == "bingkai":
        fname = (frames or {}).get(layout)
        img = t_bingkai(c, os.path.join(asset_dir, os.path.basename(fname)) if fname and asset_dir else None)
    else:
        img = BY_ID[tid][2](c)
    if layout == "strip":
        sheet = Image.new("RGB", (W4R, H4R), (255, 255, 255))
        sheet.paste(img, (0, 0))
        sheet.paste(img, (STRIP_W, 0))
        d = ImageDraw.Draw(sheet)   # tanda potong tipis di tengah atas & bawah
        for y0, y1 in ((0, 24), (H4R - 24, H4R)):
            d.line([STRIP_W, y0, STRIP_W, y1], fill=(150, 150, 150), width=2)
        return sheet
    return img


def test_sheet(name=""):
    img = Image.new("RGB", (W4R, H4R), (255, 255, 255))
    d = ImageDraw.Draw(img)
    cols = [(230, 57, 70), (241, 196, 15), (46, 204, 113), (52, 152, 219), (155, 89, 182), (30, 30, 30)]
    for i, col in enumerate(cols):
        d.rectangle([80 + i * 175, 300, 80 + i * 175 + 160, 700], fill=col)
    for i in range(12):
        v = int(i * 255 / 11)
        d.rectangle([80 + i * 87, 760, 80 + i * 87 + 80, 900], fill=(v, v, v))
    d.rectangle([20, 20, W4R - 20, H4R - 20], outline=(0, 0, 0), width=6)
    text_c(d, W4R / 2, 120, "TES PRINTER FOTO", T.F("bebas", 130), (20, 20, 20))
    text_c(d, W4R / 2, 1000, "4R · 4x6 inci · 1200x1800 px", T.F("mono", 40), (60, 60, 60))
    text_c(d, W4R / 2, 1080, name or "", T.F("mono", 34), (60, 60, 60))
    text_c(d, W4R / 2, 1180, datetime.now().strftime("%d-%m-%Y %H:%M"), T.F("mono", 34), (60, 60, 60))
    text_c(d, W4R / 2, 1500, "Garis tepi harus terlihat utuh di semua sisi", T.F("sans", 38), (90, 90, 90))
    return img
