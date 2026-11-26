"""Komposisi struk foto 1-bit untuk printer Receipt Photobooth 80mm (576 dot)."""
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

try:
    import qrcode
except ImportError:  # QR opsional
    qrcode = None

BLACK, WHITE = 0, 255

LAYOUTS = {
    # nama: (jumlah foto, label)
    "solo": (1, "SOLO · 1 FOTO"),
    "duo": (2, "DUO · 2 FOTO"),
    "strip": (3, "STRIP · 3 FOTO"),
    "grid": (4, "GRID · 4 FOTO"),
}

_FONT_CANDIDATES = {
    True: ["arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    False: ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
_MONO_CANDIDATES = ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
_font_cache = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key in _font_cache:
        return _font_cache[key]
    here = os.path.dirname(os.path.abspath(__file__))
    custom = os.path.join(here, "fonts", "mono.ttf" if mono else ("bold.ttf" if bold else "regular.ttf"))
    for name in [custom] + (_MONO_CANDIDATES if mono else _FONT_CANDIDATES[bold]):
        try:
            f = ImageFont.truetype(name, size)
            _font_cache[key] = f
            return f
        except OSError:
            continue
    f = ImageFont.load_default(size=size)
    _font_cache[key] = f
    return f


# ---------- gaya cetak (foto -> 1-bit) ----------

def _prep(img, size):
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, size, Image.LANCZOS)
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=1)
    return g


def _halftone(g, cell=8):
    w, h = g.size
    small = g.resize((max(1, w // cell), max(1, h // cell)), Image.BILINEAR)
    out = Image.new("L", (w, h), WHITE)
    d = ImageDraw.Draw(out)
    sw, sh = small.size
    px = small.load()
    max_r = cell * 0.72
    for y in range(sh):
        for x in range(sw):
            darkness = 1 - px[x, y] / 255
            r = max_r * (darkness ** 0.8)
            if r < 0.6:
                continue
            cx, cy = x * cell + cell / 2, y * cell + cell / 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLACK)
    return out


ASCII_RAMP = "@#S%?*+;:,. "   # gelap -> terang


def _ascii(g, cell_w=7):
    """Foto -> susunan huruf/simbol (font mono)."""
    w, h = g.size
    f = font(12, mono=True)
    cw = cell_w
    ch = int(cw * 1.75)
    cols, rows = max(1, w // cw), max(1, h // ch)
    small = g.resize((cols, rows), Image.BILINEAR)
    small = ImageOps.autocontrast(small, cutoff=2)
    out = Image.new("L", (w, h), WHITE)
    d = ImageDraw.Draw(out)
    px = small.load()
    n = len(ASCII_RAMP) - 1
    ox = (w - cols * cw) // 2
    for y in range(rows):
        line = "".join(ASCII_RAMP[int(px[x, y] / 255 * n)] for x in range(cols))
        for x, chx in enumerate(line):
            if chx != " ":
                d.text((ox + x * cw, y * ch), chx, font=f, fill=BLACK)
    return out.point(lambda v: WHITE if v > 140 else BLACK)


def _coloring(g):
    """Foto -> garis luar tebal untuk diwarnai (coloring page)."""
    s = g.filter(ImageFilter.GaussianBlur(2.2))
    s = ImageOps.posterize(s, 3)
    e = s.filter(ImageFilter.FIND_EDGES)
    e = ImageOps.autocontrast(e)
    lines = e.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(3))
    lines = lines.filter(ImageFilter.MedianFilter(3))
    out = ImageOps.invert(lines)
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, out.width - 1, out.height - 1), outline=BLACK, width=3)
    return out


def stylize(img, size, style="dither", brightness=1.0):
    """Kembalikan gambar mode 'L' sesuai gaya yang dipilih."""
    if style == "bw":
        # Hitam-putih natural studio: continuous tone grayscale murni, tajam & bersih
        img = ImageOps.exif_transpose(img).convert("RGB")
        im = ImageOps.fit(img, size, Image.LANCZOS)
        g = ImageOps.autocontrast(im.convert("L"), cutoff=0.5)
        g = g.filter(ImageFilter.UnsharpMask(radius=1.8, percent=120, threshold=2))
        return ImageEnhance.Contrast(g).enhance(1.08)

    g = _prep(img, size)
    if brightness != 1.0:
        g = g.point(lambda v: max(0, min(255, int(v * brightness))))
    if style == "halftone":
        out = _halftone(g)
    elif style == "ascii":
        out = _ascii(g)
    elif style == "mewarnai":
        out = _coloring(g)
    elif style == "kontras":
        out = g.point(lambda v: WHITE if v > 120 else BLACK)
    elif style == "sketsa":
        e = g.filter(ImageFilter.GaussianBlur(1)).filter(ImageFilter.FIND_EDGES)
        e = ImageOps.invert(ImageOps.autocontrast(e))
        out = e.point(lambda v: WHITE if v > 200 else BLACK)
    else:  # dither Floyd–Steinberg
        g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=80))
        out = g.convert("1").convert("L")
    return out


# ---------- komposisi struk ----------

def _text_center(d, y, text, f, width):
    w = d.textlength(text, font=f)
    d.text(((width - w) / 2, y), text, font=f, fill=BLACK)
    bbox = f.getbbox(text)
    return y + (bbox[3] - bbox[1]) + 8


def _wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _dashed(d, y, x0, x1, dash=14, gap=10, h=4):
    x = x0
    while x < x1:
        d.rectangle((x, y, min(x + dash, x1), y + h - 1), fill=BLACK)
        x += dash + gap
    return y + h


def make_qr_with_logo(url, logo=None, box_size=1, border=1, target_size=None, as_rgb=False):
    """
    Buat QR code dengan opsi logo di tengah.
    Menggunakan ERROR_CORRECT_H (kapasitas koreksi ~30%) agar QR code tetap 100% terbaca
    meskipun ada logo di tengahnya.
    """
    import qrcode
    ec = qrcode.constants.ERROR_CORRECT_H if logo else qrcode.constants.ERROR_CORRECT_M
    q = qrcode.QRCode(border=border, box_size=box_size, error_correction=ec)
    q.add_data(url)
    q.make(fit=True)
    qr = q.make_image(fill_color="black", back_color="white").convert("RGBA")

    if target_size:
        k = max(1, target_size // qr.width)
        qr = qr.resize((qr.width * k, qr.height * k), Image.NEAREST)

    if logo:
        try:
            if isinstance(logo, str) and os.path.exists(logo):
                lg = Image.open(logo).convert("RGBA")
            elif hasattr(logo, "convert"):
                lg = logo.convert("RGBA")
            else:
                lg = None

            if lg:
                max_dim = int(qr.width * 0.22)
                lg = lg.copy()
                lg.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                pad = max(2, int(qr.width * 0.02))
                box_w = lg.width + pad * 2
                box_h = lg.height + pad * 2
                badge = Image.new("RGBA", (box_w, box_h), (255, 255, 255, 255))
                badge.paste(lg, (pad, pad), lg)

                px = (qr.width - box_w) // 2
                py = (qr.height - box_h) // 2
                qr.paste(badge, (px, py))
        except Exception:
            pass

    if as_rgb:
        return qr.convert("RGB")
    return qr.convert("L").point(lambda v: 255 if v > 127 else 0)


def compose_receipt(photos, layout="strip", style="dither", caption="", show_logo=True,
                    event_name="NAMA EVENT", logo_path=None, qr_url=None, number=None,
                    width=576, brightness=1.0, footer="TERIMA KASIH", template="klasik",
                    custom=None, asset_dir=None, now=None, social=None, opts=None, ph_cache=None,
                    has_living=False):
    """photos: list PIL.Image. Return PIL.Image mode '1' lebar `width`."""
    import templates as T

    logo = logo_src = None
    if show_logo and logo_path and os.path.exists(logo_path):
        logo_src = Image.open(logo_path).convert("RGBA")
        logo = logo_src.copy()
        logo.thumbnail((int(width * 0.6), 140))
        if logo.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", logo.size, "white")
            bg.paste(logo, mask=logo.split()[-1])
            logo = bg
        logo = ImageOps.grayscale(logo).convert("1").convert("L")

    qr = None
    if qr_url and qrcode:
        qr = make_qr_with_logo(qr_url, logo=logo_src if show_logo else None, box_size=1, border=1)

    ctx = T.Ctx(list(photos), layout if layout in LAYOUTS else "strip",
                lambda im, size: stylize(im, size, style, brightness),
                event=event_name, caption=caption, number=number, qr=qr, logo=logo, width=width,
                logo_src=logo_src, asset_dir=asset_dir, now=now, social=social, opts=opts,
                ph_cache=ph_cache, footer=footer, has_living=has_living)
    return T.render(template, ctx, custom)


def stylize_sample(img, style, width=576, brightness=1.0):
    return stylize(img, (width, int(width * 2 / 3)), style, brightness)


# ---------- blok tambahan di bawah struk (undian, pose, buku tamu) ----------

def append_extras(img, extras, width=576, logo_path=None):
    """img: struk mode '1'. extras: {'lucky': '0127', 'poses': [...], 'guestbook': {name, message, signature(PIL)}}."""
    if not extras or not any(extras.get(k) for k in ("lucky", "poses", "guestbook", "living")):
        return img
    import templates as T
    p = T.Paper(width)
    W, L, R = width, T.M, width - T.M
    p.y = 6
    p.y = p.dashed(h=3, x0=L, x1=R) + 22
    gb = extras.get("guestbook") or {}
    if gb.get("message") or gb.get("signature") is not None:
        p.y = p.center("BUKU TAMU", T.F("monob", 17), spacing=4) + 14
        if gb.get("message"):
            p.para_center("“" + gb["message"].strip() + "”", T.F("hand", 38), max_w=R - L, line_gap=4)
        sig = gb.get("signature")
        if sig is not None:
            s = sig.convert("RGBA")
            bg = Image.new("RGB", s.size, "white")
            bg.paste(s, mask=s.split()[3])
            g = ImageOps.grayscale(bg)
            bbox = ImageOps.invert(g).getbbox()
            if bbox:
                g = g.crop(bbox)
                g.thumbnail((360, 130))
                ink = g.point(lambda v: 255 if v < 160 else 0)
                x = (W - g.width) // 2
                p.y += 8
                p.img.paste(T.K, (x, p.y, x + g.width, p.y + g.height), ink)
                p.y += g.height + 6
        if gb.get("name"):
            p.d.rectangle((W / 2 - 150, p.y, W / 2 + 150, p.y + 1), fill=T.K)
            p.y = p.center(gb["name"].strip()[:40], T.F("sansb", 20), y=p.y + 10) + 18
        p.y += 6
    poses = [x for x in (extras.get("poses") or []) if x]
    if poses:
        p.y = p.center("TANTANGAN POSE", T.F("monob", 17), spacing=4) + 14
        for i, t in enumerate(poses, 1):
            for line in p.wrap(f"{i}. {t}", T.F("sans", 20), R - L):
                p.text(L, p.y, line, T.F("sans", 20))
                p.y += 28
        p.y += 14
    if extras.get("lucky"):
        h = 120
        p.d.rounded_rectangle((L, p.y, R, p.y + h), radius=16, fill=T.K)
        p.center("NOMOR UNDIAN", T.F("monob", 18), y=p.y + 16, fill=T.P, spacing=4)
        p.center(str(extras["lucky"]), T.F("bebas", 70), y=p.y + 42, fill=T.P)
        p.y += h + 10
        p.y = p.center("Simpan struk ini untuk undian doorprize", T.F("sans", 17)) + 10
    if extras.get("living"):
        p.y = living_block(p, extras["living"], L, R, logo_path=logo_path)
    block = p.finish(bottom_pad=24)
    out_mode = img.mode if img.mode in ("1", "L", "RGB") else "L"
    out = Image.new(out_mode, (width, img.height + block.height), 255 if out_mode in ("L", "RGB") else 1)
    out.paste(img, (0, 0))
    out.paste(block.convert(out_mode), (0, img.height))
    return out


def living_block(p, url, L, R, logo_path=None):
    """QR Living Photo (unik per cetakan) + petunjuk singkat + logo kecil di bawah QR."""
    import templates as T

    logo_src = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_src = Image.open(logo_path).convert("RGBA")
        except Exception:
            logo_src = None

    p.y = p.dashed(h=3, x0=L, x1=R) + 18
    m = make_qr_with_logo(url, logo=logo_src, target_size=184).convert("1")

    top = p.y
    p.img.paste(m, (L, top))
    x = L + m.width + 18
    p.text(x, top + 6, "LIVING PHOTO", T.F("monob", 20), spacing=3)
    big = 46
    while big > 26 and max(p.tw("Scan untuk putar", T.F("bebas", big)), p.tw("video kamu", T.F("bebas", big))) > R - x:
        big -= 2                                     # judul selalu muat di samping QR
    p.text(x, top + 38 + (46 - big) // 2, "Scan untuk putar", T.F("bebas", big))
    p.text(x, top + 82, "video kamu", T.F("bebas", big))
    desc_lines = p.wrap("Scan pakai kamera HP lalu pilih video sekali. Video diputar tiap kali di-scan, tersimpan di HP kamu saja.",
                        T.F("sans", 16), R - x)
    for i, line in enumerate(desc_lines):
        p.text(x, top + 132 + i * 21, line, T.F("sans", 16))

    text_bottom = top + 132 + len(desc_lines) * 21
    qr_bottom = top + m.height

    # Gambar logo tepat di bawah qrcode video living (rata dengan teks di sampingnya)
    logo_bottom = qr_bottom
    if logo_src:
        try:
            lg = logo_src.copy()
            # Lebar logo proporsional dengan lebar QR code agar pas tepat di bawahnya
            lg.thumbnail((int(m.width * 0.92), 42), Image.Resampling.LANCZOS)
            if lg.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", lg.size, "white")
                bg.paste(lg, mask=lg.split()[-1])
                lg = bg
            lg = ImageOps.grayscale(lg).convert("1").convert("L")

            # Posisikan horizontal tepat di tengah kolom QR code (di bawah QR code, bukan di tengah kertas)
            x_logo = L + (m.width - lg.width) // 2
            # Posisikan vertikal agar sejajar / sama rata dengan bagian bawah teks di sampingnya
            y_logo = max(qr_bottom + 8, text_bottom - lg.height)
            p.paste(lg, x_logo, y_logo)
            logo_bottom = y_logo + lg.height
        except Exception:
            pass

    p.y = max(text_bottom, logo_bottom) + 16
    return p.y


def host_copy(img, width=576, label="ARSIP TUAN RUMAH"):
    """Salinan untuk tuan rumah: tambah pita hitam di atas."""
    import templates as T
    p = T.Paper(width, h=80)
    p.d.rectangle((0, 0, width, 56), fill=T.K)
    p.center(label, T.F("monob", 22), y=17, fill=T.P, spacing=4)
    p.y = 66
    head = p.finish(bottom_pad=0)
    out_mode = img.mode if img.mode in ("1", "L", "RGB") else "L"
    out = Image.new(out_mode, (width, img.height + head.height), 255 if out_mode in ("L", "RGB") else 1)
    out.paste(head.convert(out_mode), (0, 0))
    out.paste(img, (0, head.height))
    return out
