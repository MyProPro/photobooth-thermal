"""Foto contoh untuk preview di Template Studio.

Pakai foto sesi terakhir kalau ada (output/sessions), kalau belum ada pakai ilustrasi.
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SESS = os.path.join(BASE, "output", "sessions")


def _illustration(seed):
    r = random.Random(seed)
    W, H = 1200, 900
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(200 - 90 * t), int(190 - 80 * t), int(170 - 60 * t)))
    for k in range(40):
        rr = 300 - k * 7
        d.ellipse((900 - rr, 150 - rr, 900 + rr, 150 + rr), fill=(230 - k, 225 - k, 210 - k))
    people = [1, 2, 3, 2][seed % 4]
    xs = [W / 2] if people == 1 else ([W * .35, W * .65] if people == 2 else [W * .25, W * .5, W * .75])
    for i, x in enumerate(xs):
        s = 1.0 - 0.15 * (people - 1)
        d.ellipse((x - 260 * s, 560, x + 260 * s, 1300), fill=(40 + i * 30, 50, 70 + i * 20))
        d.rectangle((x - 45 * s, 470, x + 45 * s, 600), fill=(190, 140, 110))
        for k in range(30):
            rx, ry = (135 - k * 2) * s, (170 - k * 2) * s
            c = 150 + k * 3
            d.ellipse((x - rx - k * 1.5, 300 - ry, x + rx - k * 1.5, 300 + ry), fill=(c, int(c * .78), int(c * .65)))
        d.chord((x - 150 * s, 120, x + 150 * s, 400), 180, 360, fill=(30, 25, 20))
        d.arc((x - 55 * s, 330, x + 55 * s, 400), 20, 160, fill=(90, 30, 30), width=6)
    r.random()
    return im.filter(ImageFilter.GaussianBlur(1.2))


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
