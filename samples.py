"""Foto contoh untuk preview di Template Studio.

Pakai foto sesi terakhir kalau ada (output/sessions), kalau belum ada pakai ilustrasi.
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SESS = os.path.join(BASE, "output", "sessions")


# ---------- ilustrasi contoh (dipakai kalau belum ada foto) ----------
_S = 2                       # supersampling supaya tepi halus
_cache = {}


def _grad(W, H, top, bottom):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)))
    return im


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _person(im, cx, hy, hs, skin, hair, style, top, kind, extras=()):
    """Gambar 1 orang (kartun flat). cx, hy = pusat kepala; hs = skala."""
    S = _S
    d = ImageDraw.Draw(im, "RGBA")
    X = lambda v: int(cx * S + v * hs * S)  # noqa: E731
    Y = lambda v: int(hy * S + v * hs * S)  # noqa: E731
    if "veil" in extras:
        d.polygon([(X(-70), Y(-80)), (X(70), Y(-80)), (X(230), Y(520)), (X(-230), Y(520))], fill=(255, 255, 255, 120))
    if style == "long":
        d.rounded_rectangle((X(-95), Y(-95), X(95), Y(210)), radius=int(70 * hs * S), fill=hair)
    # badan
    d.ellipse((X(-185), Y(150), X(185), Y(620)), fill=top)
    if kind == "suit":
        d.polygon([(X(-48), Y(150)), (X(48), Y(150)), (X(0), Y(330))], fill=(250, 250, 250))
        d.polygon([(X(-48), Y(150)), (X(-8), Y(300)), (X(-80), Y(240))], fill=_shade(top, 0.75))
        d.polygon([(X(48), Y(150)), (X(8), Y(300)), (X(80), Y(240))], fill=_shade(top, 0.75))
    elif kind == "dress":
        d.chord((X(-70), Y(110), X(70), Y(230)), 0, 180, fill=skin)
        for k in range(-3, 4):
            d.ellipse((X(k * 20 - 6), Y(232 - abs(k) * 6), X(k * 20 + 6), Y(244 - abs(k) * 6)), fill=(235, 225, 210))
    else:
        d.chord((X(-55), Y(120), X(55), Y(200)), 0, 180, fill=_shade(top, 0.8))
    # leher
    d.rounded_rectangle((X(-32), Y(60), X(32), Y(170)), radius=int(14 * hs * S), fill=_shade(skin, 0.88))
    # telinga & kepala
    for sx in (-1, 1):
        d.ellipse((X(sx * 78 - 14), Y(-10), X(sx * 78 + 14), Y(30)), fill=_shade(skin, 0.93))
    d.ellipse((X(-75), Y(-92), X(75), Y(92)), fill=skin)
    # rambut depan
    if style in ("short", "long", "bun"):
        d.chord((X(-82), Y(-102), X(82), Y(40)), 180, 360, fill=hair)
        d.pieslice((X(-82), Y(-102), X(60), Y(20)), 200, 300, fill=hair)
    if style == "bun":
        d.ellipse((X(-38), Y(-150), X(38), Y(-80)), fill=hair)
    if style == "kid":
        d.chord((X(-80), Y(-98), X(80), Y(10)), 180, 360, fill=hair)
    # wajah
    for sx in (-1, 1):
        d.ellipse((X(sx * 30 - 9), Y(-8), X(sx * 30 + 9), Y(14)), fill=(30, 24, 22))
        d.ellipse((X(sx * 30 - 3), Y(-5), X(sx * 30 + 2), Y(1)), fill=(255, 255, 255))
        d.arc((X(sx * 30 - 18), Y(-36), X(sx * 30 + 18), Y(-14)), 200, 340, fill=_shade(hair, 0.9), width=max(2, int(5 * hs * S)))
        d.ellipse((X(sx * 46 - 16), Y(22), X(sx * 46 + 16), Y(40)), fill=(235, 120, 120, 90))
    d.chord((X(-32), Y(22), X(32), Y(70)), 0, 180, fill=(120, 30, 40))
    d.chord((X(-24), Y(23), X(24), Y(40)), 0, 180, fill=(255, 255, 255))
    if "glasses" in extras:
        for sx in (-1, 1):
            d.rounded_rectangle((X(sx * 30 - 26), Y(-24), X(sx * 30 + 26), Y(22)), radius=int(10 * hs * S),
                                outline=(20, 20, 20), width=max(2, int(6 * hs * S)))
        d.line((X(-4), Y(-4), X(4), Y(-4)), fill=(20, 20, 20), width=max(2, int(5 * hs * S)))
    if "bowtie" in extras:
        d.polygon([(X(0), Y(165)), (X(-34), Y(148)), (X(-34), Y(184))], fill=(25, 25, 30))
        d.polygon([(X(0), Y(165)), (X(34), Y(148)), (X(34), Y(184))], fill=(25, 25, 30))
    if "crown" in extras:
        for k in range(-3, 4):
            d.ellipse((X(k * 22 - 13), Y(-104 + abs(k) * 5), X(k * 22 + 13), Y(-78 + abs(k) * 5)),
                      fill=[(250, 250, 250), (245, 190, 200), (255, 230, 170)][k % 3])
    if "hat" in extras:
        col = extras[-1] if isinstance(extras[-1], tuple) else (230, 80, 60)
        d.polygon([(X(-48), Y(-80)), (X(48), Y(-80)), (X(10), Y(-230))], fill=col)
        for k in range(1, 4):
            yy = -80 - k * 36
            w = 48 - k * 11
            d.line((X(-w), Y(yy), X(w + 4), Y(yy + 8)), fill=(255, 255, 255), width=max(2, int(6 * hs * S)))
        d.ellipse((X(-6), Y(-250), X(26), Y(-218)), fill=(255, 220, 90))


def _bokeh(im, rnd, n, colors):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    W, H = im.size
    for _ in range(n):
        r = rnd.randint(20, 90) * _S
        x, y = rnd.randint(0, W), rnd.randint(0, int(H * 0.7))
        c = rnd.choice(colors)
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (rnd.randint(50, 110),))
    lay = lay.filter(ImageFilter.GaussianBlur(6 * _S))
    im.paste(lay, (0, 0), lay)


def _illustration(seed):
    """4 adegan contoh: pengantin, pesta teman, keluarga, dua sahabat."""
    seed = seed % 4
    if seed in _cache:
        return _cache[seed].copy()
    rnd = random.Random(seed * 7 + 3)
    W, H = 1200 * _S, 900 * _S
    if seed == 0:  # pengantin
        im = _grad(W, H, (246, 226, 222), (214, 182, 176))
        _bokeh(im, rnd, 26, [(255, 255, 255), (255, 214, 220), (255, 238, 200)])
        d = ImageDraw.Draw(im, "RGBA")
        for k in range(30):  # karangan bunga melengkung
            t = k / 29
            x = int((120 + 960 * t) * _S)
            y = int((150 - 120 * (1 - (2 * t - 1) ** 2)) * _S)
            r = rnd.randint(22, 38) * _S
            d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice([(255, 255, 255), (244, 180, 190), (120, 160, 110)]))
        _person(im, 470, 430, 1.05, (244, 206, 180), (70, 45, 35), "long", (250, 248, 244), "dress", ("veil", "crown"))
        _person(im, 760, 400, 1.1, (222, 176, 140), (30, 24, 22), "short", (38, 40, 52), "suit", ("bowtie",))
    elif seed == 1:  # pesta teman
        im = _grad(W, H, (64, 70, 120), (30, 28, 60))
        _bokeh(im, rnd, 30, [(255, 210, 120), (255, 120, 160), (120, 200, 255)])
        d = ImageDraw.Draw(im, "RGBA")
        for _ in range(140):  # konfeti
            x, y = rnd.randint(0, W), rnd.randint(0, H)
            c = rnd.choice([(255, 210, 80), (255, 110, 130), (120, 220, 200), (255, 255, 255)])
            d.rectangle((x, y, x + 10 * _S, y + 18 * _S), fill=c)
        for bx, col in ((110, (240, 80, 90)), (1080, (255, 200, 70))):  # balon
            d.ellipse((int((bx - 70) * _S), 40 * _S, int((bx + 70) * _S), 220 * _S), fill=col)
            d.line((bx * _S, 220 * _S, int((bx + 10) * _S), 420 * _S), fill=(240, 240, 240), width=3 * _S)
        _person(im, 300, 470, 0.92, (236, 196, 166), (40, 30, 26), "bun", (255, 120, 90), "tee", ("hat", (90, 200, 220)))
        _person(im, 600, 430, 1.0, (200, 150, 116), (25, 22, 20), "short", (255, 214, 90), "tee", ("glasses", "hat", (255, 110, 130)))
        _person(im, 900, 470, 0.92, (244, 210, 186), (110, 70, 40), "long", (120, 200, 160), "tee", ("hat", (255, 200, 70)))
    elif seed == 2:  # keluarga
        im = _grad(W, H, (220, 236, 240), (176, 204, 196))
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse((880 * _S, -120 * _S, 1240 * _S, 240 * _S), fill=(255, 236, 170, 220))
        _bokeh(im, rnd, 16, [(255, 255, 255), (255, 240, 200)])
        _person(im, 380, 380, 1.0, (232, 192, 160), (50, 36, 28), "long", (120, 150, 200), "tee")
        _person(im, 820, 360, 1.05, (214, 170, 134), (30, 26, 24), "short", (70, 110, 90), "tee", ("glasses",))
        _person(im, 600, 600, 0.72, (240, 204, 176), (60, 40, 30), "kid", (255, 170, 80), "tee")
    else:  # dua sahabat
        im = _grad(W, H, (250, 236, 210), (226, 196, 160))
        _bokeh(im, rnd, 24, [(255, 255, 255), (255, 220, 160), (255, 200, 200)])
        _person(im, 430, 430, 1.05, (240, 200, 170), (35, 28, 25), "bun", (220, 90, 80), "tee", ("glasses",))
        _person(im, 770, 440, 1.05, (206, 160, 124), (55, 40, 30), "short", (60, 90, 160), "tee")
    out = im.resize((1200, 900), Image.LANCZOS)
    _cache[seed] = out
    return out.copy()


def sample_photos(n=9):
    try:
        dirs = sorted((os.path.join(SESS, d) for d in os.listdir(SESS)),
                      key=os.path.getmtime, reverse=True)
        for d in dirs:
            files = sorted(f for f in os.listdir(d) if f.startswith("foto_"))
            if files:
                ims = [Image.open(os.path.join(d, f)).convert("RGB") for f in files]
                return [ims[i % len(ims)] for i in range(n)]
    except OSError:
        pass
    base = [_illustration(i) for i in range(4)]
    return [base[i % 4] for i in range(n)]
