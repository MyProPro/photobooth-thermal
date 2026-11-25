"""Koleksi template struk hitam-putih untuk printer Receipt Photobooth 80mm.

Setiap template menerima Ctx dan mengembalikan PIL.Image mode 'L' (isi hanya 0/255).
Semua template mendukung layout: solo (1), duo (2), strip (3), grid (4 foto).
Tambah template baru: buat fungsi t_xxx(c) lalu daftarkan di TEMPLATES.
"""
import os
import random
import math
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE, "fonts")
K, P = 0, 255  # hitam, putih (paper)
M = 20  # jarak aman kiri-kanan untuk teks (printer tidak mencetak sampai tepi)

HARI = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU", "MINGGU"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

# ---------------------------------------------------------------- bahasa cetak
# Teks template ditulis dalam Bahasa Indonesia. Kalau event memilih bahasa cetak
# English, Paper menerjemahkan teks lewat tabel di bawah (per thread, aman untuk
# server multi-thread). Teks buatan user (nama event, caption, template custom)
# tidak ikut diterjemahkan kecuali sama persis dengan teks bawaan.
import re as _re
import threading as _threading

_TL = _threading.local()
PRINT_LANGS = [("id", "Bahasa Indonesia"), ("en", "English")]

DAYS_EN = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def set_lang(lang):
    _TL.lang = "en" if str(lang or "").lower().startswith("en") else "id"


def get_lang():
    return getattr(_TL, "lang", "id")


def month_name(m):
    """m: 1..12"""
    return (MONTHS_EN if get_lang() == "en" else BULAN)[m - 1]


def day_name(wd):
    """wd: 0=Senin .. 6=Minggu"""
    return (DAYS_EN if get_lang() == "en" else HARI)[wd]


EN = {
    # umum
    "NAMA EVENT": "EVENT NAME", "TERIMA KASIH": "THANK YOU",
    "Scan untuk unduh": "Scan to download", "versi digital": "the digital", "berwarna.": "color copy.",
    "scan untuk versi digital": "scan for the digital copy", "unduh versi digital": "download digital copy",
    "SOLO · 1 FOTO": "SOLO · 1 PHOTO", "DUO · 2 FOTO": "DUO · 2 PHOTOS", "STRIP · 3 FOTO": "STRIP · 3 PHOTOS",
    "GRID · 4 FOTO": "GRID · 4 PHOTOS", "FEED · 9 FOTO": "FEED · 9 PHOTOS",
    "MOMEN BAHAGIA": "HAPPY MOMENTS",
    # tiket / pass
    "TANGGAL": "DATE", "JAM": "TIME", "SOBEK DI SINI": "TEAR HERE", "NAMA": "NAME",
    # koran
    "Kabar Booth": "Booth News", "HARGA: 1 SENYUM": "PRICE: 1 SMILE",
    "TAMU INI TERTANGKAP KAMERA SEDANG BAHAGIA": "GUEST CAUGHT ON CAMERA BEING HAPPY",
    "Foto: dok. Photobooth": "Photo: Photobooth archive", "BERSAMBUNG KE HAL. 2 >": "CONTINUED ON P. 2 >",
    "Baca edisi digital": "Read the digital", "(foto berwarna)": "edition (in color)", "di HP kamu.": "on your phone.",
    # majalah
    "JUGA DI EDISI INI": "ALSO IN THIS ISSUE", "HARGA: GRATIS": "PRICE: FREE",
    # struk belanja
    "Jl. Kenangan No. 1": "1 Memory Lane", "NO. TRX": "TRX NO.", "KASIR": "CASHIER", "GRATIS": "FREE",
    "1 x SENYUM LEBAR": "1 x BIG SMILE", "1 x TAWA LEPAS": "1 x GOOD LAUGH", "1 x KERTAS STRUK": "1 x RECEIPT PAPER",
    "BAHAGIA": "HAPPY", "TUNAI": "CASH", "KENANGAN": "MEMORIES", "KEMBALI": "CHANGE",
    "BARANG YANG SUDAH DIFOTO": "ITEMS ALREADY PHOTOGRAPHED", "TIDAK DAPAT DITUKAR": "CANNOT BE EXCHANGED",
    # profil sosial
    "www.websitekamu.com": "www.yourwebsite.com",
    # kalender
    "MIN": "SUN", "SEN": "MON", "SEL": "TUE", "RAB": "WED", "KAM": "THU", "JUM": "FRI", "SAB": "SAT",
    # ramalan
    "RAMALAN": "FORTUNE", "REZEKI": "LUCK", "JODOH": "LOVE", "KARIER": "CAREER",
    "Warna keberuntungan: hitam (kata printer)": "Lucky color: black (says the printer)",
    "Hari ini senyummu jadi alasan orang lain ikut bahagia.": "Today your smile is the reason someone else is happy.",
    "Rezeki datang dari arah tak terduga. Mungkin dari doorprize.": "Luck comes from unexpected places. Maybe the door prize.",
    "Seseorang diam-diam menyimpan fotomu. Itu kamu, barusan.": "Someone is secretly keeping your photo. That was you, just now.",
    "Kesabaranmu akan segera dibalas dengan makanan enak.": "Your patience will soon be rewarded with good food.",
    "Bintangmu terang malam ini. Lampu booth-nya juga.": "Your star shines bright tonight. So do the booth lights.",
    "Hal baik datang bertiga: kamu, foto ini, dan struknya.": "Good things come in threes: you, this photo and the receipt.",
    "Jangan lupa minum air putih, lalu pose lagi.": "Remember to drink water, then pose again.",
    "Liburan sudah memanggil. Jawab teleponnya.": "A vacation is calling. Pick up the phone.",
    "Kamu akan bertemu orang baru yang menyenangkan hari ini.": "You will meet someone delightful today.",
    "Pose berikutnya akan jadi foto terbaikmu tahun ini.": "Your next pose will be your best photo this year.",
    # boarding
    "Sini": "Here", "Bahagia": "Happy", "TAMU ISTIMEWA": "VIP GUEST",
    # sertifikat
    "SERTIFIKAT": "CERTIFICATE", "Dengan ini menyatakan bahwa": "This is to certify that",
    "Pemegang sertifikat ini": "The holder of this certificate",
    "telah resmi dinyatakan sebagai": "has officially been declared",
    "RESMI": "OFFICIAL", "Ketua Panitia Senyum": "Chair, Smile Committee",
    "CAKEP MAKSIMAL | tanpa filter, tanpa editan": "MAXIMUM GORGEOUS | no filter, no edits",
    "CANTIK 95% | 5% sisanya ketinggalan di rumah": "95% BEAUTIFUL | the other 5% was left at home",
    "GANTENG 95% | 5% lagi masih loading": "95% HANDSOME | the other 5% is still loading",
    "JELEK 3% | 97% sisanya kece parah": "3% UGLY | the other 97% is stunning",
    "AURA +1000 | terdeteksi dari jarak 5 meter": "AURA +1000 | detected from 5 meters away",
    "MAIN CHARACTER | yang lain cuma figuran": "MAIN CHARACTER | everyone else is an extra",
    "SPEK IDAMAN MERTUA | sopan, wangi, fotogenik": "IN-LAW APPROVED | polite, fragrant, photogenic",
    "BUKAN KALENG-KALENG | kualitas ekspor": "THE REAL DEAL | export quality",
    "SLAY TOTAL | no debat": "TOTAL SLAY | no debate",
    "GLOW UP BERHASIL | versi terbaik hari ini": "GLOW UP COMPLETE | today's best version",
    "SENYUM 100% ORI | bukan KW": "100% GENUINE SMILE | not a knockoff",
    "VIBES JUARA | satu ruangan ikut bahagia": "CHAMPION VIBES | the whole room is happy",
    "PALING FOTOGENIK | kamera pun naksir": "MOST PHOTOGENIC | even the camera has a crush",
    "KEREN TAPI SANTUY | low effort, high result": "COOL BUT CHILL | low effort, high result",
    # resep
    "Spesialis Senyum": "Smile Specialist", "Pro  :": "For  :", "Tamu istimewa": "Special guest",
    "Tgl  :": "Date :", "Obat tidak perlu ditebus. Gratis.": "No need to pay for this medicine. It's free.",
    "Senyum lebar": "Big smile", "3x sehari sesudah makan": "3x a day after meals",
    "Tertawa lepas": "Hearty laugh", "sesuai kebutuhan": "as needed",
    "Foto bareng teman": "Photo with friends", "min. 1x per acara": "at least 1x per event",
    "Pelukan hangat": "Warm hug", "2x sehari": "2x a day",
    "Liburan": "Vacation", "1x sebulan, jangan ditunda": "1x a month, don't postpone",
    "Air putih": "Water", "8 gelas sehari": "8 glasses a day",
    "Tidur cukup": "Enough sleep", "tiap malam": "every night",
    "Dengar lagu favorit": "Favorite song", "sebelum tidur": "before bed",
    # tes kecocokan
    "LAB PHOTOBOOTH": "PHOTOBOOTH LAB", "HASIL TES KECOCOKAN": "COMPATIBILITY TEST RESULT",
    "TINGKAT KECOCOKAN": "COMPATIBILITY LEVEL", "PEMERIKSAAN": "TEST", "HASIL": "RESULT",
    "Selera humor": "Sense of humor", "Selera makan": "Food taste", "Kekompakan pose": "Pose sync",
    "Level bucin": "Lovey-dovey level", "KESIMPULAN:": "CONCLUSION:",
    "Sangat cocok. Segera foto lagi.": "A perfect match. Take another photo soon.",
    "Cocok banget, tinggal tentukan tanggal.": "So compatible, just pick a date.",
    "Kompak! Pertahankan.": "In sync! Keep it up.", "Chemistry di atas rata-rata.": "Above-average chemistry.",
    "Satu frekuensi. Langka!": "Same wavelength. Rare!",
    # kartu pos
    "KARTU POS": "POSTCARD", "Untuk:": "To:", "Pesan:": "Message:", "Dari:": "From:",
    # komik
    "Eh, kameranya udah nyala?": "Wait, is the camera on?", "Senyum! Satu, dua...": "Smile! One, two...",
    "Ini dicetak di struk?!": "This prints on a receipt?!", "Pose andalan, go!": "Signature pose, go!",
    "Satu lagi, satu lagi!": "One more, one more!", "Siapa yang kedip?": "Who blinked?",
    "Fix ini masuk feed.": "This is going on my feed.", "Kok aku paling kece?": "Why do I look the best?",
    "Gaya bebas!": "Freestyle!", "Jangan lupa bahagia.": "Don't forget to be happy.",
    "Mana fotografernya?": "Where's the photographer?", "Cekrek!": "Click!", "TAMAT": "THE END",
    # hari (kalender)
    "Senin": "Monday", "Selasa": "Tuesday", "Rabu": "Wednesday", "Kamis": "Thursday",
    "Jumat": "Friday", "Sabtu": "Saturday", "Minggu": "Sunday",
    # blok tambahan (imaging.py)
    "BUKU TAMU": "GUESTBOOK", "TANTANGAN POSE": "POSE CHALLENGE", "NOMOR UNDIAN": "LUCKY NUMBER",
    "Simpan struk ini untuk undian doorprize": "Keep this receipt for the door prize draw",
    "ARSIP TUAN RUMAH": "HOST COPY",
    "Scan untuk putar": "Scan to play", "video kamu": "your video",
    "VERSI DEMO - BELUM BERLISENSI": "DEMO VERSION - UNLICENSED",
    "Scan pakai kamera HP lalu pilih video sekali. Video diputar tiap kali di-scan, tersimpan di HP kamu saja.":
        "Scan with your phone camera and pick a video once. It plays on every scan, saved on your phone only.",
    # foto 4R (photo.py)
    "Tampil memukau malam ini": "Stunning tonight", "SENYUM 100% · GAYA MAKSIMAL": "100% SMILE · MAXIMUM STYLE",
}

# teks yang berisi data (nama event, nomor, tanggal): (pola, ganti)
EN_RX = [(_re.compile(a), b) for a, b in [
    (r"^EDISI SPESIAL · (.*)$", r"SPECIAL EDITION · \1"),
    (r"^EDISI NO\. (.*)$", r"ISSUE NO. \1"),
    (r"^EDISI #(.*)$", r"ISSUE #\1"),
    (r"^Laporan langsung dari booth foto (.*)$", r"Live report from the \1 photo booth"),
    (r"^Sebuah momen langka berhasil diabadikan di (.*?)\. Menurut saksi mata.*$",
     r"A rare moment was captured at \1. According to witnesses, the smiles seen were one hundred "
     r"percent genuine and completely unforced. The editors confirm this photo was printed directly "
     r"on Receipt Photobooth paper, with no filter other than happiness. As of press time, the line in front of "
     r"the booth keeps growing."),
    (r"^(\d+) x POSE ANDALAN$", r"\1 x SIGNATURE POSE"),
    (r"^CATATAN: (.*)$", r"NOTE: \1"),
    (r"^Seru banget di (.*)!$", r"So much fun at \1!"),
    (r"^Live dari (.*)!$", r"Live from \1!"),
    (r"^Kenangan dari (.*)$", r"Memories from \1"),
    (r"^Momen #(\d+) di (.*)$", r"Moment #\1 at \2"),
    (r"^HARI INI · (.*)$", r"TODAY · \1"),
    (r"^Angka keberuntungan: (.*)$", r"Lucky numbers: \1"),
    (r"^Diperiksa oleh: Lab Photobooth (.*)$", r"Checked by: Photobooth Lab \1"),
    (r"^No\. Sampel : (.*)$", r"Sample No. : \1"),
    (r"^Ditetapkan di (.*)$", r"Issued at \1"),
    (r"^Praktik: (.*)$", r"Practice: \1"),
    (r"^SIP (.*)$", r"LIC \1"),
    (r"^Suatu hari di (.*)$", r"One day at \1"),
    (r"^S (.+)$", None),          # aturan pakai resep: "S <aturan>"
    (r"^(.*) · UNDIAN #(.*)$", r"\1 · DRAW #\2"),
    (r"^(.*)  ·  UNDIAN #(.*)$", r"\1  ·  DRAW #\2"),
    (r"^Template ini tidak mendukung layout '(.*)'$", r"This template does not support the '\1' layout"),
]]


def tr(text):
    """Terjemahkan teks cetak sesuai bahasa event (thread ini). Bahasa Indonesia: tidak diubah."""
    if not text or get_lang() != "en" or getattr(_TL, "off", False) or not isinstance(text, str):
        return text
    hit = EN.get(text)
    if hit is not None:
        return hit
    for rx, rep in EN_RX:
        m = rx.match(text)
        if m:
            if rep is None:          # "S <aturan>"
                inner = EN.get(m.group(1))
                return "S " + inner if inner else text
            return m.expand(rep)
    return text


class no_translate:
    """with no_translate(): ... -> teks buatan user (template custom) tidak diterjemahkan."""
    def __enter__(self):
        self._old = getattr(_TL, "off", False)
        _TL.off = True

    def __exit__(self, *a):
        _TL.off = self._old

# ---------------------------------------------------------------- font
_FILES = {
    "bebas": ("BebasNeue-Regular.ttf", None),
    "black": ("ArchivoBlack-Regular.ttf", None),
    "mono": ("SpaceMono-Regular.ttf", None),
    "monob": ("SpaceMono-Bold.ttf", None),
    "hand": ("Caveat.ttf", "Bold"),
    "serif": ("PlayfairDisplay.ttf", "Regular"),
    "serifb": ("PlayfairDisplay.ttf", "Bold"),
    "serifk": ("PlayfairDisplay.ttf", "Black"),
    "sans": ("Inter.ttf", "Regular"),
    "sansb": ("Inter.ttf", "Bold"),
    "geo": ("JosefinSans.ttf", "SemiBold"),
    "geob": ("JosefinSans.ttf", "Bold"),
}
_FALLBACK = {
    "bebas": ["impact.ttf", "DejaVuSans-Bold.ttf"], "black": ["ariblk.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["consola.ttf", "DejaVuSansMono.ttf"], "monob": ["consolab.ttf", "DejaVuSansMono-Bold.ttf"],
    "hand": ["segoepr.ttf", "DejaVuSans.ttf"], "serif": ["georgia.ttf", "DejaVuSerif.ttf"],
    "serifb": ["georgiab.ttf", "DejaVuSerif-Bold.ttf"], "serifk": ["georgiab.ttf", "DejaVuSerif-Bold.ttf"],
    "sans": ["arial.ttf", "DejaVuSans.ttf"], "sansb": ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "geo": ["century.ttf", "DejaVuSans.ttf"], "geob": ["gothicb.ttf", "DejaVuSans-Bold.ttf"],
}
_cache = {}


def F(name, size):
    key = (name, size)
    if key in _cache:
        return _cache[key]
    fname, var = _FILES[name]
    f = None
    try:
        f = ImageFont.truetype(os.path.join(FONT_DIR, fname), size)
        if var:
            try:
                f.set_variation_by_name(var)
            except Exception:  # noqa: BLE001
                pass
    except OSError:
        for alt in _FALLBACK[name]:
            try:
                f = ImageFont.truetype(alt, size)
                break
            except OSError:
                continue
    if f is None:
        f = ImageFont.load_default(size=size)
    _cache[key] = f
    return f


# ---------------------------------------------------------------- konteks
class Ctx:
    def __init__(self, photos, layout, stylize_fn, event="NAMA EVENT", caption="",
                 number=None, qr=None, logo=None, width=576, now=None, logo_src=None, asset_dir=None,
                 social=None, opts=None, ph_cache=None, footer="TERIMA KASIH", has_living=False):
        self.photos = photos
        self.layout = layout
        self.n = {"solo": 1, "duo": 2, "strip": 3, "grid": 4, "feed": 9}.get(layout, 3)
        self._stylize = stylize_fn
        self.event = (event or "").strip() or "NAMA EVENT"
        self.caption = (caption or "").strip()[:40]
        self.number = number
        self.qr = qr        # PIL 'L' atau None
        self.logo = logo    # PIL 'L' atau None
        self.W = width
        self.now = now or datetime.now()
        self.logo_src = logo_src      # logo asli (RGBA) untuk template custom
        self.asset_dir = asset_dir    # folder aset event (frame PNG)
        self.social = social or {}    # username/website untuk template Profil Sosmed
        self.opts = opts or {}        # pilihan teks (gelar sertifikat, rute boarding, dll.)
        self._ph = ph_cache if ph_cache is not None else {}   # bisa dibagi antar template (lebih cepat)
        self.footer = (footer or "").strip() or "TERIMA KASIH"
        self.has_living = has_living

    # foto yang sudah dijadikan 1-bit sesuai gaya
    def ph(self, i, w, h):
        key = (i, w, h)
        if key not in self._ph:
            if i < len(self.photos) and self.photos[i] is not None:
                self._ph[key] = self._stylize(self.photos[i], (w, h))
            else:
                im = Image.new("L", (w, h), P)
                d = ImageDraw.Draw(im)
                d.rectangle((0, 0, w - 1, h - 1), outline=K, width=3)
                d.line((0, 0, w, h), fill=K, width=2)
                d.line((0, h, w, 0), fill=K, width=2)
                self._ph[key] = im
        return self._ph[key]

    @property
    def no(self):
        return f"{self.number:04d}" if isinstance(self.number, int) else "----"

    @property
    def date_num(self):
        return self.now.strftime("%d.%m.%Y")

    @property
    def time(self):
        return self.now.strftime("%H:%M")

    @property
    def date_long(self):
        return f"{self.now.day} {month_name(self.now.month)} {self.now.year}"

    @property
    def day(self):
        return day_name(self.now.weekday())


# ---------------------------------------------------------------- kanvas
class Paper:
    def __init__(self, W, h=6000):
        self.W = W
        self.img = Image.new("L", (W, h), P)
        self.d = ImageDraw.Draw(self.img)
        self.y = 0

    def tw(self, text, f, spacing=0):
        text = tr(text)
        return self.d.textlength(text, font=f) + spacing * max(0, len(text) - 1)

    def text(self, x, y, text, f, fill=K, spacing=0, stroke=0, stroke_fill=K):
        """Gambar teks dengan sisi atas glyph tepat di y. Return tinggi."""
        text = tr(text)
        bb = f.getbbox(text or " ")
        top = bb[1]
        if spacing:
            cx = x
            for ch in text:
                self.d.text((cx, y - top), ch, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
                cx += self.d.textlength(ch, font=f) + spacing
        else:
            self.d.text((x, y - top), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        return bb[3] - bb[1]

    def center(self, text, f, y=None, fill=K, spacing=0, x0=0, x1=None, stroke=0, stroke_fill=K):
        x1 = self.W if x1 is None else x1
        y = self.y if y is None else y
        w = self.tw(text, f, spacing)
        h = self.text(x0 + (x1 - x0 - w) / 2, y, text, f, fill, spacing, stroke, stroke_fill)
        return y + h

    def right(self, text, f, y, x1=None, fill=K):
        x1 = self.W if x1 is None else x1
        return self.text(x1 - self.tw(text, f), y, text, f, fill)

    def wrap(self, text, f, max_w):
        text = tr(text)
        lines, cur = [], ""
        for wd in text.split():
            t = (cur + " " + wd).strip()
            if self.tw(t, f) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines

    def para_center(self, text, f, max_w=None, line_gap=8, fill=K, x0=0, x1=None):
        x1 = self.W if x1 is None else x1
        max_w = max_w or (x1 - x0)
        for line in self.wrap(text, f, max_w):
            self.y = self.center(line, f, fill=fill, x0=x0, x1=x1) + line_gap
        return self.y

    def rule(self, h=3, x0=0, x1=None, y=None):
        x1 = self.W if x1 is None else x1
        y = self.y if y is None else y
        self.d.rectangle((x0, y, x1 - 1, y + h - 1), fill=K)
        return y + h

    def dashed(self, h=3, dash=12, gap=8, x0=0, x1=None, y=None):
        x1 = self.W if x1 is None else x1
        y = self.y if y is None else y
        x = x0
        while x < x1:
            self.d.rectangle((x, y, min(x + dash, x1) - 1, y + h - 1), fill=K)
            x += dash + gap
        return y + h

    def dots(self, r=3, step=14, x0=0, x1=None, y=None):
        x1 = self.W if x1 is None else x1
        y = self.y if y is None else y
        x = x0 + r
        while x < x1 - r:
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=K)
            x += step
        return y + r

    def paste(self, im, x, y):
        self.img.paste(im, (int(x), int(y)))

    def barcode(self, x, y, w, h, seed="0"):
        rnd = random.Random(str(seed))
        cx = x
        bar = True
        while cx < x + w:
            m = rnd.choice([2, 2, 3, 4, 6])
            if bar:
                self.d.rectangle((cx, y, min(cx + m, x + w) - 1, y + h - 1), fill=K)
            cx += m
            bar = not bar

    def diamond(self, cx, cy, r, fill=K):
        self.d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=fill)

    def ornament(self, y, w=220, x_center=None):
        cx = self.W / 2 if x_center is None else x_center
        self.d.rectangle((cx - w / 2, y, cx - 14, y + 1), fill=K)
        self.d.rectangle((cx + 14, y, cx + w / 2, y + 1), fill=K)
        self.diamond(cx, y + 1, 7)
        self.diamond(cx - 22, y + 1, 3)
        self.diamond(cx + 22, y + 1, 3)
        return y + 8

    def qr_row(self, c, text_lines=("Scan untuk unduh", "versi digital", "berwarna."), size=170, x=0):
        if c.qr is None:
            if getattr(c, "logo", None) is not None and not getattr(c, "has_living", False):
                lg = c.logo.copy()
                lg.thumbnail((int(self.W * 0.25), 45))
                self.paste(lg, (self.W - lg.width) / 2, self.y)
                self.y += lg.height + 12
            return self.y
        q = qr_fit(c.qr, size)
        self.paste(q, x, self.y)
        f = F("sans", 22)
        lh = 30
        ty = self.y + (size - lh * len(text_lines)) / 2 + 4
        for t in text_lines:
            self.text(x + size + 22, ty, t, f)
            ty += lh
        self.y += size
        if getattr(c, "logo", None) is not None and not getattr(c, "has_living", False):
            lg = c.logo.copy()
            lg.thumbnail((int(self.W * 0.25), 45))
            self.paste(lg, (self.W - lg.width) / 2, self.y + 10)
            self.y += lg.height + 18
        return self.y

    def finish(self, bottom_pad=40):
        h = int(self.y + bottom_pad)
        return self.img.crop((0, 0, self.W, h)).point(lambda v: P if v > 127 else K)


def qr_fit(qr, size):
    """Perbesar QR dengan kelipatan bulat supaya modulnya rata (mudah discan)."""
    k = max(1, size // qr.width)
    return qr.resize((qr.width * k, qr.width * k), Image.NEAREST)


def slots(layout, x, y, w, gap=12, solo_r=0.75, strip_r=2 / 3, grid_r=1.0, duo_r=0.75):
    """Posisi foto (x, y, w, h) untuk layout; return (list, bottom)."""
    if layout == "solo":
        h = int(w * solo_r)
        return [(x, y, w, h)], y + h
    if layout == "duo":
        h = int(w * duo_r)
        return [(x, y, w, h), (x, y + h + gap, w, h)], y + 2 * h + gap
    if layout == "grid":
        s = (w - gap) // 2
        h = int(s * grid_r)
        r = [(x, y, s, h), (x + s + gap, y, s, h),
             (x, y + h + gap, s, h), (x + s + gap, y + h + gap, s, h)]
        return r, y + 2 * h + gap
    if layout == "feed":
        s = (w - 2 * gap) // 3
        r = [(x + (i % 3) * (s + gap), y + (i // 3) * (s + gap), s, s) for i in range(9)]
        return r, y + 3 * s + 2 * gap
    h = int(w * strip_r)
    r = [(x, y + i * (h + gap), w, h) for i in range(3)]
    return r, y + 3 * h + 2 * gap


def put_photos(p, c, rects, border=0, frame_gap=0):
    for i, (x, y, w, h) in enumerate(rects):
        p.paste(c.ph(i, w, h), x, y)
        if border:
            o = frame_gap + border
            p.d.rectangle((x - o, y - o, x + w + o - 1, y + h + o - 1), outline=K, width=border)


# ================================================================ TEMPLATE

def t_klasik(c):
    p = Paper(c.W)
    p.y = 24
    p.para_center(c.event.upper(), F("black", 46), line_gap=10)
    p.y = p.center("PHOTOBOOTH", F("mono", 20), y=p.y + 4, spacing=8) + 12
    p.y = p.center(f"{c.date_num}  —  {c.time}", F("mono", 20)) + 22
    p.y = p.dashed() + 22
    rects, p.y = slots(c.layout, 0, p.y, c.W)
    put_photos(p, c, rects)
    p.y += 26
    if c.caption:
        p.para_center(c.caption, F("hand", 46), max_w=c.W - 2 * M, line_gap=6)
        p.y += 8
    p.y = p.dashed() + 18
    f = F("mono", 20)
    p.text(M, p.y, f"NO. {c.no}", f)
    p.right({"solo": "SOLO · 1 FOTO", "duo": "DUO · 2 FOTO", "strip": "STRIP · 3 FOTO", "grid": "GRID · 4 FOTO", "feed": "FEED · 9 FOTO"}[c.layout], f, p.y, x1=c.W - M)
    p.y += 46
    p.qr_row(c, x=M)
    p.y += 30
    p.y = p.center(c.footer, F("bebas", 52))
    return p.finish()


def t_polaroid(c):
    p = Paper(c.W)
    p.y = 26
    p.y = p.center(c.event.upper(), F("monob", 20), spacing=6) + 10
    p.y = p.center(c.date_long, F("hand", 30)) + 28
    hand = F("hand", 34)
    rnd = random.Random(c.no)

    def card(pw, ph_, i, label, pad=16, bottom=64):
        cw, ch = pw + pad * 2, ph_ + pad + bottom
        im = Image.new("L", (cw, ch), P)
        d = ImageDraw.Draw(im)
        im.paste(c.ph(i, pw, ph_), (pad, pad))
        d.rectangle((0, 0, cw - 1, ch - 1), outline=K, width=3)
        if label:
            label = tr(label)
            f = hand if bottom > 50 else F("hand", 26)
            tw = d.textlength(label, font=f)
            bb = f.getbbox(label)
            d.text(((cw - tw) / 2, pad + ph_ + (bottom - (bb[3] - bb[1])) / 2 - bb[1]), label, font=f, fill=K)
        return im

    def rot(im, a):
        return im.rotate(a, resample=Image.NEAREST, expand=True, fillcolor=P)

    if c.layout == "solo":
        im = rot(card(500, 500, 0, c.caption or c.date_num, bottom=80), -1.5)
        p.paste(im, (c.W - im.width) / 2, p.y)
        p.y += im.height + 24
    elif c.layout in ("strip", "duo"):
        labels = [f"#{i + 1}" for i in range(c.n)]
        labels[-1] = c.caption or labels[-1]
        for i in range(c.n):
            im = rot(card(440, 330, i, labels[i]), [-2, 2, -1.5][i])
            x = [16, c.W - im.width - 16, 24][i]
            p.paste(im, x, p.y)
            p.y += im.height - 6
        p.y += 26
    else:
        cells = []
        for i in range(4):
            cells.append(rot(card(232, 232, i, f"#{i + 1}", pad=12, bottom=44), rnd.choice([-2.5, -1.5, 1.5, 2.5])))
        cw = max(im.width for im in cells)
        row_h = [max(cells[0].height, cells[1].height), max(cells[2].height, cells[3].height)]
        for r in range(2):
            for col in range(2):
                im = cells[r * 2 + col]
                x = (c.W / 2 - cw) / 2 + col * c.W / 2
                p.paste(im, x, p.y)
            p.y += row_h[r] + 4
        p.y += 18
        if c.caption:
            p.para_center(c.caption, F("hand", 44))
    if c.caption and c.layout == "solo":
        pass
    p.y += 6
    p.y = p.center(f"— No. {c.no} —", F("mono", 18)) + 26
    if c.qr is not None:
        q = qr_fit(c.qr, 150)
        p.paste(q, (c.W - 150) / 2, p.y)
        p.y += 160
        p.y = p.center("scan untuk versi digital", F("hand", 28))
    return p.finish()


def t_film(c):
    p = Paper(c.W)
    p.y = 22
    p.y = p.center(c.event.upper(), F("bebas", 60)) + 10
    p.y = p.center("PHOTOBOOTH FILM  ·  ISO 400", F("mono", 18), spacing=2) + 22
    top = p.y
    inner_x, inner_w = 64, c.W - 128
    mono = F("monob", 16)
    # konten dulu (perlu tahu tinggi film)
    y = top + 44
    if c.layout == "solo":
        rects = [(inner_x, y, inner_w, int(inner_w * 1.2))]
    elif c.layout in ("strip", "duo"):
        h = int(inner_w * (0.72 if c.n == 3 else 0.85))
        rects = [(inner_x, y + i * (h + 46), inner_w, h) for i in range(c.n)]
    else:
        s = (inner_w - 14) // 2
        rects = [(inner_x, y, s, s), (inner_x + s + 14, y, s, s),
                 (inner_x, y + s + 46, s, s), (inner_x + s + 14, y + s + 46, s, s)]
    bottom = max(r[1] + r[3] for r in rects) + 44
    p.d.rectangle((0, top, c.W - 1, bottom), fill=K)
    # lubang sprocket
    yy = top + 12
    while yy + 18 < bottom - 6:
        for hx in (16, c.W - 16 - 26):
            p.d.rounded_rectangle((hx, yy, hx + 26, yy + 18), radius=4, fill=P)
        yy += 34
    put_photos(p, c, rects)
    # label frame
    p.text(inner_x, top + 16, c.date_num, mono, fill=P)
    p.right("PB-400", mono, top + 16, x1=inner_x + inner_w, fill=P)
    seen_rows = sorted({r[1] + r[3] for r in rects})
    for k, ry in enumerate(seen_rows):
        ly = ry + 15
        p.d.polygon([(inner_x, ly), (inner_x + 10, ly + 6), (inner_x, ly + 12)], fill=P)
        p.text(inner_x + 18, ly, f"{k + 1}A", mono, fill=P)
        p.right(f"{k + 1}  >>", mono, ly, x1=inner_x + inner_w, fill=P)
    p.y = bottom + 26
    if c.caption:
        p.para_center(c.caption, F("hand", 46))
        p.y += 6
    f = F("mono", 18)
    p.text(M, p.y, f"FRAME NO. {c.no}", f)
    p.right(c.time, f, p.y, x1=c.W - M)
    p.y += 40
    p.qr_row(c, size=150, x=M)
    return p.finish()


def t_tiket(c):
    p = Paper(c.W)
    m = 8
    p.y = 18
    top = p.y
    p.y += 22
    p.y = p.center("ADMIT ONE", F("bebas", 104)) + 10
    p.y = p.dots(r=2, step=10, x0=40, x1=c.W - 40, y=p.y + 4) + 18
    p.para_center(c.event.upper(), F("black", 34), max_w=c.W - 80, line_gap=8)
    p.y += 12
    # kotak info
    cols = [("TANGGAL", c.now.strftime("%d %b").upper()), ("JAM", c.time), ("NO.", c.no)]
    bw = (c.W - 2 * 30 - 2 * 10) / 3
    for i, (lab, val) in enumerate(cols):
        x = 30 + i * (bw + 10)
        p.d.rectangle((x, p.y, x + bw, p.y + 86), outline=K, width=3)
        p.text(x + 12, p.y + 12, lab, F("mono", 14))
        p.text(x + 12, p.y + 38, val, F("bebas", 42))
    p.y += 86 + 26
    rects, p.y = slots(c.layout, 30, p.y, c.W - 60, gap=14)
    put_photos(p, c, rects, border=4, frame_gap=0)
    p.y += 22
    if c.caption:
        p.para_center(c.caption, F("hand", 42), max_w=c.W - 80)
    p.y += 10
    p.d.rectangle((m, top, c.W - m - 1, p.y), outline=K, width=4)
    # perforasi
    p.y += 26
    p.dots(r=3, step=13, y=p.y)
    p.y += 16
    p.y = p.center("SOBEK DI SINI", F("mono", 14), spacing=4) + 22
    # stub
    stub_top = p.y
    p.y += 20
    p.text(30, p.y, "STUB", F("bebas", 46))
    p.right(f"NO. {c.no}", F("monob", 20), p.y + 14, x1=c.W - 30)
    p.y += 62
    if c.qr is not None:
        p.barcode(30, p.y, c.W - 60 - 150, 100, seed=c.no)
        p.paste(qr_fit(c.qr, 130), c.W - 30 - 130, p.y - 10)
        p.y += 130
    else:
        p.barcode(30, p.y, c.W - 60, 90, seed=c.no)
        p.y += 110
    p.d.rectangle((m, stub_top, c.W - m - 1, p.y), outline=K, width=4)
    p.y += 10
    return p.finish()


def t_pass(c):
    p = Paper(c.W)
    x0, x1 = 10, c.W - 10
    p.y = 14
    # lubang tali
    p.d.rounded_rectangle((c.W / 2 - 50, p.y, c.W / 2 + 50, p.y + 16), radius=8, outline=K, width=3)
    p.y += 30
    top = p.y
    p.d.rounded_rectangle((x0, top, x1, top + 120), radius=26, fill=K, corners=(True, True, False, False))
    p.center("GUEST PASS", F("bebas", 80), y=top + 20, fill=P)
    p.y = top + 120 + 26
    inner = 34
    rects, p.y = slots(c.layout, x0 + inner, p.y, x1 - x0 - 2 * inner, gap=10,
                       solo_r=1.0, strip_r=0.62)
    put_photos(p, c, rects, border=3, frame_gap=5)
    p.y += 30
    lab, val = F("mono", 15), F("sansb", 26)
    fields = [("NAMA", None), ("EVENT", c.event), ("TANGGAL", f"{c.date_long} · {c.time}")]
    for name, v in fields:
        p.text(x0 + inner, p.y, name, lab)
        p.y += 26
        if v is None:
            p.dashed(h=2, dash=6, gap=6, x0=x0 + inner, x1=x1 - inner, y=p.y + 34)
            p.y += 52
        else:
            for line in p.wrap(v, val, x1 - x0 - 2 * inner):
                p.y += p.text(x0 + inner, p.y, line, val) + 8
            p.y += 14
    # akses
    p.d.rectangle((x0 + inner, p.y, x1 - inner, p.y + 70), fill=K)
    p.center("ACCESS: ALL AREA", F("bebas", 48), y=p.y + 12, fill=P)
    p.y += 70 + 22
    p.barcode(x0 + inner, p.y, x1 - x0 - 2 * inner, 64, seed=c.no)
    p.y += 72
    p.y = p.center(f"* {c.no} *", F("mono", 16)) + 14
    if c.caption:
        p.para_center(c.caption, F("hand", 40), max_w=x1 - x0 - 2 * inner)
    p.y += 16
    p.d.rounded_rectangle((x0, top, x1, p.y), radius=26, outline=K, width=5)
    p.y += 24
    if c.qr is not None:
        p.qr_row(c, size=140, x=20)
    return p.finish()


def t_koran(c):
    p = Paper(c.W)
    W = c.W
    p.y = 20
    p.y = p.rule(2) + 10
    newspaper_name = (c.opts.get("newspaper_name") or "Kabar Booth").strip() or "Kabar Booth"
    fsize = 76
    while fsize > 36 and p.tw(newspaper_name, F("serifk", fsize)) > W - 20:
        fsize -= 4
    p.y = p.center(newspaper_name, F("serifk", fsize)) + 12
    p.y = p.rule(5) + 3
    p.y = p.rule(1) + 8
    f = F("mono", 14)
    p.text(M, p.y, f"EDISI NO. {c.no}", f)
    p.center(f"{c.day}, {c.now.strftime('%d %b %Y').upper()}", f, y=p.y)
    p.right("HARGA: 1 SENYUM", f, p.y, x1=c.W - M)
    p.y += 22
    p.y = p.rule(1) + 22
    head = c.caption.upper() if c.caption else "TAMU INI TERTANGKAP KAMERA SEDANG BAHAGIA"
    for line in p.wrap(head, F("serifb", 44), W):
        p.y = p.center(line, F("serifb", 44)) + 8
    p.y += 6
    p.y = p.center(f"Laporan langsung dari booth foto {c.event}", F("serif", 20)) + 22
    # foto: 1 besar + sisanya kecil
    big_h = int(W * 0.7)
    p.paste(c.ph(0, W, big_h), 0, p.y)
    p.y += big_h + 6
    p.text(M, p.y, "Foto: dok. Photobooth", F("mono", 13))
    p.y += 26
    rest = c.n - 1
    if rest:
        gap = 10
        sw = (W - gap * (rest - 1)) // rest
        sh = int(sw * {1: 0.6, 2: 0.7}.get(rest, 1.0))
        for i in range(rest):
            p.paste(c.ph(i + 1, sw, sh), i * (sw + gap), p.y)
        p.y += sh + 22
    # artikel 2 kolom
    body = (f"Sebuah momen langka berhasil diabadikan di {c.event}. Menurut saksi mata, senyum "
            "yang terlihat seratus persen asli dan tanpa paksaan. Redaksi memastikan foto ini "
            "dicetak langsung di atas kertas Receipt Photobooth, tanpa filter apa pun kecuali kebahagiaan. "
            "Hingga berita ini diturunkan, antrean di depan booth terus bertambah.")
    fb = F("serif", 18)
    colw = (W - 2 * M - 24) // 2
    lines = p.wrap(body, fb, colw)
    half = (len(lines) + 1) // 2
    ty = p.y
    for k, col in enumerate([lines[:half], lines[half:]]):
        yy = ty
        for line in col:
            p.text(M + k * (colw + 24), yy, line, fb)
            yy += 26
    p.d.rectangle((M + colw + 11, ty, M + colw + 12, ty + half * 26), fill=K)
    p.y = ty + half * 26 + 18
    p.right("BERSAMBUNG KE HAL. 2 >", F("monob", 14), p.y, x1=c.W - M)
    p.y += 30
    p.y = p.rule(2) + 18
    p.qr_row(c, text_lines=("Baca edisi digital", "(foto berwarna)", "di HP kamu."), size=140, x=M)
    return p.finish()


def t_majalah(c):
    p = Paper(c.W)
    W = c.W
    ch = int(W * 1.3)
    p.paste(c.ph(0, W, ch), 0, 0)
    # masthead putih dengan garis hitam
    size = 150
    while size > 60 and p.tw("BOOTH", F("black", size)) > W - 36:
        size -= 4
    p.center("BOOTH", F("black", size), y=18, fill=P, stroke=5, stroke_fill=K)
    tag = f"EDISI SPESIAL · NO. {c.no}"
    ft = F("monob", 16)
    tw = p.tw(tag, ft) + 24
    p.d.rectangle(((W - tw) / 2, 196, (W + tw) / 2, 226), fill=K)
    p.center(tag, ft, y=203, fill=P)
    # cover lines di bawah
    fb = F("bebas", 50)
    lines = p.wrap(c.event.upper(), fb, W - 60)
    by = ch - 30 - len(lines) * 56 - (44 if c.caption else 0)
    for line in lines:
        w = p.tw(line, fb) + 24
        p.d.rectangle((14, by, 14 + w, by + 52), fill=K)
        p.text(26, by + 6, line, fb, fill=P)
        by += 56
    if c.caption:
        fc = F("monob", 18)
        w = p.tw(c.caption, fc) + 20
        p.d.rectangle((14, by + 4, 14 + min(w, W - 28), by + 38), fill=P)
        p.text(24, by + 12, c.caption, fc)
    p.y = ch + 20
    rest = c.n - 1
    if rest:
        p.y = p.center("JUGA DI EDISI INI", F("monob", 16), spacing=4) + 16
        gap = 10
        sw = (W - gap * (rest - 1)) // rest
        sh = int(sw * {1: 0.6, 2: 0.75}.get(rest, 1.0))
        for i in range(rest):
            p.paste(c.ph(i + 1, sw, sh), i * (sw + gap), p.y)
            p.d.rectangle((i * (sw + gap), p.y + sh - 30, i * (sw + gap) + 40, p.y + sh), fill=K)
            p.text(i * (sw + gap) + 10, p.y + sh - 24, f"0{i + 2}", F("monob", 16), fill=P)
        p.y += sh + 20
    f = F("mono", 16)
    p.text(M, p.y, c.date_num, f)
    p.right("HARGA: GRATIS", f, p.y, x1=c.W - M)
    p.y += 34
    p.qr_row(c, size=140, x=M)
    return p.finish()


def t_belanja(c):
    p = Paper(c.W)
    W = c.W
    p.y = 24
    p.para_center(c.event.upper(), F("black", 36), line_gap=8)
    p.y = p.center("PHOTOBOOTH STORE", F("monob", 20), y=p.y + 4) + 8
    p.y = p.center("Jl. Kenangan No. 1", F("mono", 18)) + 22
    p.y = p.dashed(h=2) + 16
    f = F("mono", 19)
    for k, v in [("NO. TRX", c.no), ("TANGGAL", f"{c.now.strftime('%d/%m/%Y')} {c.time}"), ("KASIR", "BOOTH-01")]:
        p.text(M, p.y, f"{tr(k):<9}: {v}", f)
        p.y += 30
    p.y += 6
    p.y = p.dashed(h=2) + 18
    rects, p.y = slots(c.layout, 0, p.y, W, gap=10)
    put_photos(p, c, rects)
    p.y += 18
    p.y = p.dashed(h=2) + 18
    items = [(f"{c.n} x POSE ANDALAN", "GRATIS"), ("1 x SENYUM LEBAR", "GRATIS"),
             ("1 x TAWA LEPAS", "GRATIS"), ("1 x KERTAS STRUK", "GRATIS")]
    for a, b in items:
        p.text(M, p.y, a, f)
        p.right(b, f, p.y, x1=c.W - M)
        p.y += 32
    if c.caption:
        p.y += 4
        for line in p.wrap("CATATAN: " + c.caption, f, W - 2 * M):
            p.text(M, p.y, line, f)
            p.y += 30
    p.y += 8
    p.y = p.rule(2) + 4
    p.y = p.rule(2) + 16
    fb = F("bebas", 56)
    p.text(M, p.y, "TOTAL", fb)
    p.right("BAHAGIA", fb, p.y, x1=c.W - M)
    p.y += 64
    for a, b in [("TUNAI", "KENANGAN"), ("KEMBALI", "0")]:
        p.text(M, p.y, a, f)
        p.right(b, f, p.y, x1=c.W - M)
        p.y += 30
    p.y += 10
    p.y = p.dashed(h=2) + 20
    p.y = p.center("BARANG YANG SUDAH DIFOTO", F("monob", 17)) + 8
    p.y = p.center("TIDAK DAPAT DITUKAR", F("monob", 17)) + 22
    p.barcode((W - 420) / 2, p.y, 420, 70, seed=c.no)
    p.y += 78
    p.y = p.center(f"{c.now.strftime('%y%m%d')}{c.no}", F("mono", 16), spacing=4) + 26
    p.qr_row(c, size=150, x=M)
    p.y += 24
    p.y = p.center(f"*** {c.footer} ***", F("monob", 20))
    return p.finish()


def t_elegan(c):
    p = Paper(c.W)
    W = c.W
    pad = 46
    p.y = 48
    p.y = p.center("MOMEN BAHAGIA", F("serif", 18), spacing=7) + 18
    p.para_center(c.event, F("serifb", 46), max_w=W - 2 * pad, line_gap=10)
    p.y += 6
    p.y = p.ornament(p.y) + 28
    rects, p.y = slots(c.layout, pad + 8, p.y, W - 2 * pad - 16, gap=24)
    put_photos(p, c, rects, border=2, frame_gap=6)
    p.y += 36
    if c.caption:
        p.para_center(c.caption, F("hand", 46), max_w=W - 2 * pad)
        p.y += 6
    p.y = p.center(c.date_long, F("serif", 24)) + 20
    p.y = p.ornament(p.y) + 24
    if c.qr is not None:
        p.paste(qr_fit(c.qr, 120), (W - 120) / 2, p.y)
        p.y += 130
        p.y = p.center("unduh versi digital", F("serif", 16)) + 10
    p.y += 30
    # bingkai ganda + ornamen sudut
    p.d.rectangle((6, 14, W - 7, p.y), outline=K, width=4)
    p.d.rectangle((18, 26, W - 19, p.y - 12), outline=K, width=1)
    for cx, cy in [(18, 26), (W - 19, 26), (18, p.y - 12), (W - 19, p.y - 12)]:
        p.diamond(cx, cy, 9)
        p.diamond(cx, cy, 4, fill=P)
    p.y += 4
    return p.finish(bottom_pad=36)


# ================================================================ PHOTOSTRIP (latar hitam)
# Catatan: area hitam besar dicetak lebih lambat & lebih panas; turunkan density printer bila perlu.

SS = 3  # supersampling untuk tepi bentuk yang halus


def _mask(w, h, draw_fn):
    m = Image.new("L", (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(m), w * SS, h * SS)
    return m.resize((w, h), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)


def shape_rounded(r):
    return lambda d, w, h: d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r * SS, fill=255)


def shape_rect(d, w, h):
    d.rectangle((0, 0, w - 1, h - 1), fill=255)


def shape_capsule(top, bottom):
    def fn(d, w, h):
        r = min(w // 2, h - 1)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255,
                            corners=(top, top, bottom, bottom))
    return fn


def shape_stamp(d, w, h):
    r = 9 * SS
    d.rectangle((r, r, w - r - 1, h - r - 1), fill=255)
    nx = max(4, round((w - 2 * r) / (2.4 * r)))
    ny = max(4, round((h - 2 * r) / (2.4 * r)))
    for i in range(nx + 1):
        x = r + (w - 2 * r) * i / nx
        for y in (r, h - r - 1):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    for j in range(ny + 1):
        y = r + (h - 2 * r) * j / ny
        for x in (r, w - r - 1):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)


def shape_arch(d, w, h):
    top, dx, f = int(h * 0.24), int(w * 0.14), int(w * 0.07)
    d.rectangle((0, top, w - 1, h - 1), fill=255)
    d.rounded_rectangle((dx, 0, w - dx - 1, int(h * 0.6)), radius=int(w * 0.22), fill=255)
    # lengkung cekung di bahu kiri & kanan
    d.rectangle((dx - f, top - f, dx, top), fill=255)
    d.ellipse((dx - 2 * f, top - 2 * f, dx, top), fill=0)
    d.rectangle((w - dx - 1, top - f, w - dx + f, top), fill=255)
    d.ellipse((w - dx - 1, top - 2 * f, w - dx + 2 * f, top), fill=0)


def shape_cartouche(d, w, h):
    ix, iy = int(w * 0.06), int(h * 0.09)
    d.rounded_rectangle((ix, iy, w - ix - 1, h - iy - 1), radius=int(min(w, h) * 0.2), fill=255)
    lob = int(h * 0.16)
    d.ellipse((0, h / 2 - lob, ix * 2.4, h / 2 + lob), fill=255)
    d.ellipse((w - ix * 2.4, h / 2 - lob, w - 1, h / 2 + lob), fill=255)
    cw = int(w * 0.12)
    d.ellipse((w / 2 - cw, 0, w / 2 + cw, iy * 2.6), fill=255)
    d.ellipse((w / 2 - cw, h - iy * 2.6, w / 2 + cw, h - 1), fill=255)


def shape_cushion(d, w, h):
    by = int(h * 0.07)
    d.rectangle((0, by, w - 1, h - by - 1), fill=255)
    d.ellipse((w * 0.08, 0, w * 0.92, by * 3), fill=255)
    d.ellipse((w * 0.08, h - by * 3, w * 0.92, h - 1), fill=255)
    rc = int(min(w, h) * 0.11)
    for cx, cy in [(0, by), (w, by), (0, h - by), (w, h - by)]:
        d.ellipse((cx - rc, cy - rc, cx + rc, cy + rc), fill=0)


def photostrip(c, shapes, gap=16, header=True, ratio=None, keyline=4, side=28, footer_label=True):
    """Kerangka umum strip latar hitam: foto bertumpuk dengan bentuk bingkai."""
    p = Paper(c.W)
    W = c.W
    pw = W - 2 * side
    ratio = ratio or {1: 1.05, 2: 0.9, 3: 0.66, 4: 0.6}[c.n]
    ph_ = int(pw * ratio)
    y = 26
    head_lines = []
    if header:
        head_lines = ["PHOTOSTRIP"] if not c.caption else p.wrap(c.caption.upper(), F("geo", 22), pw)
        y += len(head_lines) * 32 + 10
    rects = [(side, y + i * (ph_ + gap), pw, ph_) for i in range(c.n)]
    y = rects[-1][1] + ph_ + 40
    flab = F("geo", 22)
    fbig = F("geob", 56)
    small = c.date_long.upper() if (header or not c.caption) else c.caption.upper()
    small_lines = p.wrap(small, flab, pw) if footer_label else []
    big_lines = p.wrap(c.event.upper(), fbig, pw)
    foot_h = len(small_lines) * 30 + len(big_lines) * 62 + 10
    qr_h = 150 if c.qr is not None else 0
    total = y + foot_h + qr_h + 40
    p.d.rectangle((0, 0, W - 1, total), fill=K)
    ty = 30
    for line in head_lines:
        p.center(line, F("geo", 22), y=ty, fill=P, spacing=3)
        ty += 32
    for i, (x, yy, w, h) in enumerate(rects):
        shp = shapes[i % len(shapes)] if isinstance(shapes, list) else shapes(i, c.n)
        m = _mask(w, h, shp)
        if keyline:
            big = _mask(w + 2 * keyline, h + 2 * keyline,
                        lambda d, ww, hh, s=shp: s(d, ww, hh))
            p.img.paste(P, (x - keyline, yy - keyline, x + w + keyline, yy + h + keyline), big)
            p.img.paste(K, (x, yy, x + w, yy + h), m)
        p.img.paste(c.ph(i, w, h), (x, yy), m)
    ty = y
    for line in small_lines:
        p.center(line, flab, y=ty, fill=P, spacing=3)
        ty += 30
    ty += 6
    for line in big_lines:
        p.center(line, fbig, y=ty, fill=P, spacing=2)
        ty += 62
    if c.qr is not None:
        q = qr_fit(c.qr, 110)
        box = q.width + 20
        bx = (W - box) / 2
        p.d.rounded_rectangle((bx, ty + 10, bx + box, ty + 10 + box), radius=10, fill=P)
        p.paste(q, bx + 10, ty + 20)
    p.y = total
    return p.finish(bottom_pad=0)


def t_strip_rounded(c):
    return photostrip(c, [shape_rounded(18)])


def t_strip_kotak(c):
    return photostrip(c, [shape_rect], gap=30, footer_label=False, keyline=0,
                      ratio={1: 1.0, 2: 1.0, 3: 0.8, 4: 0.66}[c.n])


def t_strip_kapsul(c):
    def pick(i, n):
        if n == 1:
            return shape_capsule(True, True)
        return shape_capsule(i == 0, i == n - 1) if i in (0, n - 1) else shape_rect
    return photostrip(c, pick, gap=10, header=False,
                      ratio={1: 1.3, 2: 0.95, 3: 0.68, 4: 0.6}[c.n])


def t_strip_perangko(c):
    return photostrip(c, [shape_stamp], gap=8, header=False, keyline=0,
                      ratio={1: 1.0, 2: 0.95, 3: 0.82, 4: 0.68}[c.n])


def t_strip_vintage(c):
    return photostrip(c, [shape_arch, shape_cartouche, shape_cushion, shape_cartouche],
                      gap=22, header=False, keyline=0, side=22,
                      ratio={1: 1.05, 2: 0.9, 3: 0.72, 4: 0.62}[c.n])


# ================================================================ STRUK TES PRINTER

def test_receipt(width=576, printer_cfg=None):
    """Struk tes: penggaris tepi (cek terpotong), gradasi, ukuran teks."""
    W = width
    p = Paper(W)
    d = p.d
    p.y = 16
    # penggaris kiri-kanan: garis tepi + angka tiap 50 px
    d.rectangle((0, 0, 1, 150), fill=K)
    d.rectangle((W - 2, 0, W - 1, 150), fill=K)
    for x in range(0, W, 50):
        d.rectangle((x, 0, x + 1, 20 if x % 100 == 0 else 12), fill=K)
        if x % 100 == 0 and 0 < x < W - 40:
            p.text(x + 4, 24, str(x), F("mono", 14))
    p.y = 56
    p.y = p.center("TES PRINTER", F("black", 52)) + 14
    cfg = printer_cfg or {}
    info = f"{cfg.get('type', 'file').upper()} · {W} dot · {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    p.y = p.center(info, F("mono", 16)) + 16
    p.y = p.center("Kalau garis tepi kiri / kanan tidak tercetak,", F("sans", 17)) + 6
    p.y = p.center("tepi kertas terpotong: kecilkan lebar (paper_px).", F("sans", 17)) + 24
    # gradasi 10 tingkat (dither)
    steps = 10
    sw = W // steps
    ramp = Image.new("L", (W, 70), P)
    rd = ImageDraw.Draw(ramp)
    for i in range(steps):
        rd.rectangle((i * sw, 0, (i + 1) * sw - 1, 69), fill=int(255 * i / (steps - 1)))
    p.paste(ramp.convert("1").convert("L"), 0, p.y)
    p.y += 80
    p.y = p.center("gradasi gelap -> terang", F("mono", 14)) + 22
    for size in (14, 20, 28, 40):
        p.y = p.center(f"Teks {size}px - Photobooth", F("sans", size)) + 10
    p.y += 10
    p.barcode((W - 360) // 2, p.y, 360, 60, seed="tes")
    p.y += 80
    p.y = p.center("OK!", F("bebas", 60))
    return p.finish()


# ================================================================ PROFIL SOSMED

def _fmt_num(n):
    return f"{n:,}" if get_lang() == "en" else f"{n:,}".replace(",", ".")


def _icon(d, kind, cx, cy, s=22, w=3, fill=K):
    """Ikon garis generik (bukan logo merek)."""
    h = s / 2
    if kind == "back":
        d.line((cx - h, cy, cx + h, cy), fill=fill, width=w)
        d.line((cx - h, cy, cx - h + 10, cy - 10), fill=fill, width=w)
        d.line((cx - h, cy, cx - h + 10, cy + 10), fill=fill, width=w)
    elif kind == "dots":
        for dy in (-9, 0, 9):
            d.ellipse((cx - 3, cy + dy - 3, cx + 3, cy + dy + 3), fill=fill)
    elif kind == "grid":
        d.rectangle((cx - h, cy - h, cx + h, cy + h), outline=fill, width=w)
        for t in (-h / 3, h / 3):
            d.line((cx + t, cy - h, cx + t, cy + h), fill=fill, width=2)
            d.line((cx - h, cy + t, cx + h, cy + t), fill=fill, width=2)
    elif kind == "play":
        d.rounded_rectangle((cx - h, cy - h, cx + h, cy + h), radius=6, outline=fill, width=w)
        d.polygon([(cx - 5, cy - 7), (cx - 5, cy + 7), (cx + 7, cy)], fill=fill)
    elif kind == "tag":
        d.rounded_rectangle((cx - h, cy - h, cx + h, cy + h), radius=6, outline=fill, width=w)
        d.ellipse((cx - 5, cy - 8, cx + 5, cy + 2), outline=fill, width=2)
        d.arc((cx - 9, cy + 2, cx + 9, cy + 16), 200, 340, fill=fill, width=2)
    elif kind == "home":
        d.line([(cx - h, cy - 1), (cx, cy - h), (cx + h, cy - 1)], fill=fill, width=w, joint="curve")
        d.line([(cx - h + 4, cy - 3), (cx - h + 4, cy + h), (cx + h - 4, cy + h), (cx + h - 4, cy - 3)],
               fill=fill, width=w, joint="curve")
    elif kind == "search":
        d.ellipse((cx - h, cy - h, cx + h - 6, cy + h - 6), outline=fill, width=w)
        d.line((cx + h - 9, cy + h - 9, cx + h, cy + h), fill=fill, width=w)
    elif kind == "plus":
        d.rounded_rectangle((cx - h, cy - h, cx + h, cy + h), radius=7, outline=fill, width=w)
        d.line((cx, cy - 6, cx, cy + 6), fill=fill, width=w)
        d.line((cx - 6, cy, cx + 6, cy), fill=fill, width=w)
    elif kind == "heart":
        d.ellipse((cx - h, cy - h + 2, cx, cy + 2), outline=fill, width=w)
        d.ellipse((cx, cy - h + 2, cx + h, cy + 2), outline=fill, width=w)
        d.line([(cx - h + 1, cy - 2), (cx, cy + h), (cx + h - 1, cy - 2)], fill=fill, width=w)
    elif kind == "person_add":
        d.ellipse((cx - 9, cy - 10, cx + 3, cy + 2), outline=fill, width=2)
        d.arc((cx - 15, cy + 2, cx + 9, cy + 22), 200, 340, fill=fill, width=2)
        d.line((cx + 8, cy - 4, cx + 16, cy - 4), fill=fill, width=2)
        d.line((cx + 12, cy - 8, cx + 12, cy), fill=fill, width=2)


def _circle_img(im_l, size):
    """Gambar L -> lingkaran + mask."""
    im = im_l.resize((size, size), Image.LANCZOS) if im_l.size != (size, size) else im_l
    m = _mask(size, size, lambda d, w, h: d.ellipse((0, 0, w - 1, h - 1), fill=255))
    return im, m


def t_sosmed(c):
    W = c.W
    so = c.social or {}
    username = (so.get("username") or "").strip().lstrip("@") or "username"
    display = fill_tokens(so.get("display") or "{event}", c)
    website = (so.get("website") or "").strip() or "www.websitekamu.com"
    bio = fill_tokens(so.get("bio") or "{date_long}", c)
    rnd = random.Random(f"{c.no}-{c.now.timestamp()}")
    posts, fol, ing = (rnd.randint(500, 10000) for _ in range(3))

    p = Paper(W)
    d = p.d
    L, R = 26, W - 26
    # bar atas
    y = 34
    _icon(d, "back", L + 14, y + 14, s=26)
    p.text(L + 46, y, username, F("sansb", 28))
    _icon(d, "dots", R - 8, y + 14)
    y += 60
    # avatar + statistik
    av = 132
    ring_x, ring_y = L, y
    d.ellipse((ring_x, ring_y, ring_x + av, ring_y + av), outline=K, width=3)
    inner = av - 16
    if c.logo_src is not None:
        lg = Image.new("L", (inner, inner), P)
        ink = _ink_from_logo(c.logo_src, int(inner * 0.62), int(inner * 0.78))
        lg.paste(K, ((inner - ink.width) // 2, (inner - ink.height) // 2,
                     (inner - ink.width) // 2 + ink.width, (inner - ink.height) // 2 + ink.height), ink)
        img = lg
    else:
        img = c.ph(0, inner, inner)
    img, m = _circle_img(img, inner)
    p.img.paste(img, (ring_x + 8, ring_y + 8), m)
    sx0 = L + av + 20
    colw = (R - sx0) / 3
    for i, (num, lab) in enumerate([(posts, "Posts"), (fol, "Followers"), (ing, "Following")]):
        cx0 = sx0 + i * colw
        p.center(_fmt_num(num), F("sansb", 30), y=y + 36, x0=cx0, x1=cx0 + colw)
        p.center(lab, F("sans", 18), y=y + 78, x0=cx0, x1=cx0 + colw)
    y += av + 18
    # nama, bio, website
    p.text(L, y, display, F("sansb", 22))
    y += 32
    for line in p.wrap(bio, F("sans", 20), R - L):
        p.text(L, y, line, F("sans", 20))
        y += 28
    if c.caption:
        for line in p.wrap(c.caption, F("sans", 20), R - L):
            p.text(L, y, line, F("sans", 20))
            y += 28
    p.text(L, y, website, F("sansb", 20))
    y += 40
    # tombol
    bw = (R - L - 12 - 56) // 2
    d.rounded_rectangle((L, y, L + bw, y + 48), radius=10, fill=K)
    p.center("Follow", F("sansb", 20), y=y + 14, x0=L, x1=L + bw, fill=P)
    d.rounded_rectangle((L + bw + 6, y, L + 2 * bw + 6, y + 48), radius=10, outline=K, width=3)
    p.center("Message", F("sansb", 20), y=y + 14, x0=L + bw + 6, x1=L + 2 * bw + 6)
    d.rounded_rectangle((R - 50, y, R, y + 48), radius=10, outline=K, width=3)
    _icon(d, "person_add", R - 27, y + 24)
    y += 72
    # tab
    third = W / 3
    for i, k in enumerate(["grid", "play", "tag"]):
        _icon(d, k, third * i + third / 2, y + 16, s=26)
    y += 40
    d.rectangle((0, y, W, y + 1), fill=K)
    d.rectangle((0, y - 2, third, y + 1), fill=K)
    y += 4
    # grid foto (3 kolom gaya feed)
    gap = 4
    if c.n == 1:
        rects = [(0, y, W, W)]
    elif c.n == 2:
        s = (W - gap) // 2
        rects = [(0, y, s, s), (s + gap, y, s, s)]
    elif c.n == 3:
        s = (W - 2 * gap) // 3
        big = s * 2 + gap
        rects = [(0, y, big, big), (big + gap, y, s, s), (big + gap, y + s + gap, s, s)]
    else:
        s = (W - gap) // 2
        rects = [(0, y, s, s), (s + gap, y, s, s), (0, y + s + gap, s, s), (s + gap, y + s + gap, s, s)]
    put_photos(p, c, rects)
    y = max(r[1] + r[3] for r in rects) + 2
    # navigasi bawah
    d.rectangle((0, y, W, y + 1), fill=K)
    y += 14
    fifth = W / 5
    for i, k in enumerate(["home", "search", "plus", "heart"]):
        _icon(d, k, fifth * i + fifth / 2, y + 22, s=30)
    pa = 40
    sm, mm = _circle_img(img, pa)
    cx = int(fifth * 4 + fifth / 2)
    d.ellipse((cx - pa // 2 - 3, y + 2 - 3, cx + pa // 2 + 3, y + 2 + pa + 3), outline=K, width=2)
    p.img.paste(sm, (cx - pa // 2, y + 2), mm)
    y += 62
    # bingkai HP
    d.rounded_rectangle((3, 3, W - 4, y), radius=34, outline=K, width=4)
    p.y = y + 22
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
        p.y += 6
    return p.finish(bottom_pad=30)


# ================================================================ SOSMED LAIN (Text Feed, Micro Profile, Social Page, Video Channel)
# Tata letak profil sosial generik; ikon digambar generik, tanpa nama/logo merek apa pun.

def _social(c):
    so = c.social or {}
    return {
        "user": (so.get("username") or "").strip().lstrip("@") or "username",
        "name": fill_tokens(so.get("display") or "{event}", c),
        "web": (so.get("website") or "").strip() or tr("www.websitekamu.com"),
        "bio": fill_tokens(so.get("bio") or "{date_long}", c),
        "rnd": random.Random(f"{c.no}-{c.now.timestamp()}"),
    }


def _num_short(n):
    if n >= 1000:
        v = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
        v = v if get_lang() == "en" else v.replace(".", ",")
        return v + "K"
    return str(n)


def _avatar(c, size):
    """Avatar bulat: logo event (kalau ada) atau foto pertama."""
    if c.logo_src is not None:
        lg = Image.new("L", (size, size), P)
        ink = _ink_from_logo(c.logo_src, int(size * 0.6), int(size * 0.78))
        ox, oy = (size - ink.width) // 2, (size - ink.height) // 2
        lg.paste(K, (ox, oy, ox + ink.width, oy + ink.height), ink)
        img = lg
    else:
        img = c.ph(0, size, size)
    return _circle_img(img, size)


def _put_avatar(p, c, x, y, size, ring=0, outline=0):
    img, m = _avatar(c, size)
    if ring:
        p.d.ellipse((x - ring, y - ring, x + size + ring, y + size + ring), fill=P)
    if outline:
        p.d.ellipse((x - 1, y - 1, x + size + 1, y + size + 1), outline=K, width=outline)
    p.img.paste(img, (x, y), m)


def _photo_r(p, c, i, x, y, w, h, r=0):
    im = c.ph(i, w, h)
    if r:
        p.img.paste(im, (x, y), _mask(w, h, shape_rounded(r)))
    else:
        p.img.paste(im, (x, y))


def _collage(c, x, y, w, style="x", gap=4):
    """Susunan foto ala postingan. Return list (x, y, w, h) dan bottom."""
    n = c.n
    hw = (w - gap) // 2
    if style == "fb":
        if n == 1:
            h = int(w * 0.85)
            r = [(x, y, w, h)]
        elif n == 2:
            h = int(hw * 1.25)
            r = [(x, y, hw, h), (x + hw + gap, y, hw, h)]
        elif n == 3:
            top = int(w * 0.6)
            r = [(x, y, w, top), (x, y + top + gap, hw, hw), (x + hw + gap, y + top + gap, hw, hw)]
        else:
            top = int(w * 0.6)
            tw = (w - 2 * gap) // 3
            r = [(x, y, w, top)] + [(x + k * (tw + gap), y + top + gap, tw, tw) for k in range(3)]
    else:  # gaya micro profile / text feed
        if n == 1:
            r = [(x, y, w, int(w * 0.8))]
        else:
            H = int(w * 0.66)
            hh = (H - gap) // 2
            if n == 2:
                r = [(x, y, hw, H), (x + hw + gap, y, hw, H)]
            elif n == 3:
                r = [(x, y, hw, H), (x + hw + gap, y, hw, hh), (x + hw + gap, y + hh + gap, hw, hh)]
            else:
                r = [(x, y, hw, hh), (x + hw + gap, y, hw, hh), (x, y + hh + gap, hw, hh),
                     (x + hw + gap, y + hh + gap, hw, hh)]
    return r, max(a[1] + a[3] for a in r)


def _icon2(d, kind, cx, cy, s=24, w=3, fill=K):
    h = s / 2
    if kind == "comment":
        d.rounded_rectangle((cx - h, cy - h + 2, cx + h, cy + h - 5), radius=9, outline=fill, width=w)
        d.polygon([(cx - h + 5, cy + h - 7), (cx - h + 5, cy + h + 3), (cx - h + 14, cy + h - 7)], fill=fill)
    elif kind == "repost":
        d.line([(cx - h, cy + 2), (cx - h, cy - 6), (cx + h - 4, cy - 6)], fill=fill, width=w)
        d.polygon([(cx + h - 6, cy - 11), (cx + h + 1, cy - 6), (cx + h - 6, cy - 1)], fill=fill)
        d.line([(cx + h, cy - 2), (cx + h, cy + 6), (cx - h + 4, cy + 6)], fill=fill, width=w)
        d.polygon([(cx - h + 6, cy + 1), (cx - h - 1, cy + 6), (cx - h + 6, cy + 11)], fill=fill)
    elif kind == "send":
        d.polygon([(cx - h, cy - h + 2), (cx + h, cy), (cx - h, cy + h - 2), (cx - h + 6, cy)], outline=fill, width=w)
    elif kind == "views":
        for k, hh in enumerate((8, 14, 20)):
            x0 = cx - h + 2 + k * 8
            d.rectangle((x0, cy + h - hh, x0 + 3, cy + h), fill=fill)
    elif kind == "link":
        d.rounded_rectangle((cx - h, cy - 4, cx + 2, cy + 6), radius=5, outline=fill, width=2)
        d.rounded_rectangle((cx - 2, cy - 6, cx + h, cy + 4), radius=5, outline=fill, width=2)
    elif kind == "calendar":
        d.rounded_rectangle((cx - h + 1, cy - h + 4, cx + h - 1, cy + h - 1), radius=3, outline=fill, width=2)
        d.line((cx - h + 1, cy - h + 10, cx + h - 1, cy - h + 10), fill=fill, width=2)
    elif kind == "globe":
        d.ellipse((cx - h, cy - h, cx + h, cy + h), outline=fill, width=2)
        d.ellipse((cx - h / 2.4, cy - h, cx + h / 2.4, cy + h), outline=fill, width=2)
        d.line((cx - h, cy, cx + h, cy), fill=fill, width=2)
    elif kind == "like":
        d.rectangle((cx - h, cy - 2, cx - h + 6, cy + h), fill=fill)
        d.rounded_rectangle((cx - h + 8, cy - 4, cx + h, cy + h), radius=4, outline=fill, width=w)
        d.polygon([(cx - h + 8, cy - 2), (cx - 1, cy - h), (cx + 4, cy - h + 2), (cx + 2, cy - 3)], fill=fill)
    elif kind == "share":
        d.line([(cx - h, cy + h - 2), (cx - h, cy), (cx + h - 6, cy - 6)], fill=fill, width=w)
        d.polygon([(cx + h - 10, cy - 13), (cx + h + 1, cy - 6), (cx + h - 10, cy + 1)], fill=fill)
    elif kind == "check":
        d.ellipse((cx - h, cy - h, cx + h, cy + h), fill=fill)
        d.line([(cx - h / 2, cy), (cx - 2, cy + h / 2.4), (cx + h / 2, cy - h / 2.6)], fill=P, width=3)
    elif kind == "bell":
        d.chord((cx - h + 2, cy - h, cx + h - 2, cy + h + 6), 180, 360, outline=fill, width=2)
        d.line((cx - h, cy + 3, cx + h, cy + 3), fill=fill, width=2)


def _tabs(p, y, labels, active=0, x0=0, x1=None, size=19):
    x1 = p.W if x1 is None else x1
    cw = (x1 - x0) / len(labels)
    for i, t in enumerate(labels):
        f = F("sansb" if i == active else "sans", size)
        p.center(t, f, y=y, x0=x0 + i * cw, x1=x0 + (i + 1) * cw)
    y2 = y + size + 16
    p.d.rectangle((0, y2, p.W, y2 + 1), fill=K)
    tw = p.tw(labels[active], F("sansb", size))
    mx = x0 + active * cw + cw / 2
    p.d.rectangle((mx - tw / 2 - 6, y2 - 3, mx + tw / 2 + 6, y2 + 1), fill=K)
    return y2 + 2


def _actions(p, items, y, x0, x1):
    """Deretan ikon + angka (komentar, repost, like, ...)."""
    cw = (x1 - x0) / len(items)
    f = F("sans", 17)
    for i, (kind, label) in enumerate(items):
        cx = x0 + i * cw + 14
        (_icon2 if kind not in ("heart",) else _icon)(p.d, kind, cx, y + 12, s=22)
        if label:
            p.text(cx + 20, y + 3, label, f)
    return y + 30


def _phone_end(p, c, y):
    p.d.rounded_rectangle((3, 3, p.W - 4, y), radius=34, outline=K, width=4)
    p.y = y + 22
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
        p.y += 6
    return p.finish(bottom_pad=30)


def _wrap_text(p, x, y, text, f, max_w, lh, max_lines=None):
    lines = p.wrap(text, f, max_w)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "…"
    for line in lines:
        p.text(x, y, line, f)
        y += lh
    return y


def t_threads(c):
    s = _social(c)
    rnd = s["rnd"]
    p = Paper(c.W)
    W, L, R = c.W, 26, c.W - 26
    y = 40
    av = 92
    _put_avatar(p, c, R - av, y, av, outline=2)
    yy = y + 4
    for line in p.wrap(s["name"], F("sansb", 32), R - av - L - 16)[:2]:
        p.text(L, yy, line, F("sansb", 32))
        yy += 40
    p.text(L, yy + 2, s["user"], F("sans", 20))
    y = max(yy + 34, y + av) + 16
    y = _wrap_text(p, L, y, s["bio"], F("sans", 20), R - L, 28)
    # followers + avatar kecil bertumpuk
    for k in range(3):
        x = L + k * 18
        p.d.ellipse((x, y + 2, x + 26, y + 28), fill=P, outline=K, width=2)
        p.d.ellipse((x + 7, y + 7, x + 19, y + 19), fill=K)
    fol = rnd.randint(500, 10000)
    p.text(L + 3 * 18 + 22, y + 6, f"{_fmt_num(fol)} followers · {s['web']}", F("sans", 18))
    y += 50
    bw = (R - L - 12) // 2
    p.d.rounded_rectangle((L, y, L + bw, y + 46), radius=12, fill=K)
    p.center("Follow", F("sansb", 19), y=y + 13, x0=L, x1=L + bw, fill=P)
    p.d.rounded_rectangle((L + bw + 12, y, R, y + 46), radius=12, outline=K, width=2)
    p.center("Mention", F("sansb", 19), y=y + 13, x0=L + bw + 12, x1=R)
    y += 72
    y = _tabs(p, y, ["Posts", "Replies", "Media", "Reposts"], 0)
    # postingan
    y += 20
    pa = 52
    _put_avatar(p, c, L, y, pa)
    tx = L + pa + 14
    p.text(tx, y + 2, s["user"], F("sansb", 20))
    p.text(tx + p.tw(s["user"], F("sansb", 20)) + 10, y + 3, f"{rnd.randint(1, 23)}h", F("sans", 18))
    _icon(p.d, "dots", R - 6, y + 12)
    av_bottom = y + pa + 8
    y += 34
    post = c.caption or f"Seru banget di {c.event}!"
    y = _wrap_text(p, tx, y, post, F("sans", 20), R - tx, 28) + 10
    rects, bottom = _collage(c, tx, y, R - tx, "x", gap=6)
    for i, (x, yy, w, h) in enumerate(rects):
        _photo_r(p, c, i, x, yy, w, h, r=16)
    p.d.rectangle((L + pa // 2 - 1, av_bottom, L + pa // 2 + 1, bottom), fill=K)
    y = bottom + 16
    y = _actions(p, [("heart", _num_short(rnd.randint(500, 10000))), ("comment", str(rnd.randint(12, 300))),
                     ("repost", str(rnd.randint(5, 120))), ("send", "")], y, tx, R)
    y += 18
    return _phone_end(p, c, y)


def t_xprofil(c):
    s = _social(c)
    rnd = s["rnd"]
    p = Paper(c.W)
    W, L, R = c.W, 26, c.W - 26
    bh = 190
    p.paste(c.ph(c.n - 1, W - 8, bh), 4, 4)
    _icon(p.d, "back", L + 14, 34, s=26)
    av = 118
    ay = bh - av // 2
    _put_avatar(p, c, L, ay, av, ring=6)
    p.d.rounded_rectangle((R - 130, bh + 16, R, bh + 60), radius=22, fill=K)
    p.center("Follow", F("sansb", 20), y=bh + 28, x0=R - 130, x1=R, fill=P)
    y = ay + av + 18
    p.text(L, y, s["name"], F("sansb", 28))
    nw = p.tw(s["name"], F("sansb", 28))
    if L + nw + 40 < R:
        _icon2(p.d, "check", L + nw + 22, y + 13, s=24)
    y += 38
    p.text(L, y, "@" + s["user"], F("sans", 19))
    y += 36
    y = _wrap_text(p, L, y, s["bio"], F("sans", 20), R - L, 28) + 6
    _icon2(p.d, "link", L + 10, y + 11, s=22)
    p.text(L + 30, y, s["web"], F("sansb", 18))
    y += 30
    _icon2(p.d, "calendar", L + 10, y + 11, s=20)
    p.text(L + 30, y, f"Joined {MONTHS_EN[c.now.month - 1]} {c.now.year}", F("sans", 18))
    y += 34
    ing, fol = rnd.randint(500, 10000), rnd.randint(500, 10000)
    x = L
    for num, lab in ((ing, "Following"), (fol, "Followers")):
        p.text(x, y, _fmt_num(num), F("sansb", 19))
        x += p.tw(_fmt_num(num), F("sansb", 19)) + 6
        p.text(x, y, lab, F("sans", 19))
        x += p.tw(lab, F("sans", 19)) + 24
    y += 44
    y = _tabs(p, y, ["Posts", "Replies", "Highlights", "Media"], 0, size=18)
    # postingan
    y += 18
    pa = 54
    _put_avatar(p, c, L, y, pa)
    tx = L + pa + 12
    head = s["name"]
    p.text(tx, y + 2, head, F("sansb", 19))
    p.text(tx + p.tw(head, F("sansb", 19)) + 8, y + 3, f"@{s['user']} · {rnd.randint(1, 59)}m", F("sans", 17))
    y += 30
    post = c.caption or f"Live dari {c.event}!"
    y = _wrap_text(p, tx, y, post, F("sans", 20), R - tx, 28) + 10
    rects, bottom = _collage(c, tx, y, R - tx, "x", gap=4)
    for i, (x, yy, w, h) in enumerate(rects):
        _photo_r(p, c, i, x, yy, w, h, r=14)
    y = bottom + 14
    y = _actions(p, [("comment", str(rnd.randint(10, 400))), ("repost", _num_short(rnd.randint(50, 3000))),
                     ("heart", _num_short(rnd.randint(500, 10000))), ("views", _num_short(rnd.randint(2000, 90000)))],
                 y, tx, R)
    y += 18
    return _phone_end(p, c, y)


def t_facebook(c):
    s = _social(c)
    rnd = s["rnd"]
    p = Paper(c.W)
    W, L, R = c.W, 26, c.W - 26
    ch = 210
    p.paste(c.ph(c.n - 1, W - 8, ch), 4, 4)
    av = 150
    ay = ch - av // 2 - 10
    _put_avatar(p, c, L, ay, av, ring=6)
    y = ay + av + 16
    p.text(L, y, s["name"], F("sansb", 32))
    y += 44
    fol, frd = rnd.randint(500, 10000), rnd.randint(500, 5000)
    p.text(L, y, f"{_num_short(fol)} followers · {_fmt_num(frd)} friends", F("sans", 19))
    y += 30
    y = _wrap_text(p, L, y, s["bio"], F("sans", 19), R - L, 27)
    _icon2(p.d, "link", L + 10, y + 11, s=22)
    p.text(L + 30, y, s["web"], F("sansb", 18))
    y += 40
    bw = (R - L - 12 - 60) // 2
    p.d.rounded_rectangle((L, y, L + bw, y + 46), radius=8, fill=K)
    p.center("+ Add friend", F("sansb", 19), y=y + 13, x0=L, x1=L + bw, fill=P)
    p.d.rounded_rectangle((L + bw + 6, y, L + 2 * bw + 6, y + 46), radius=8, outline=K, width=3)
    p.center("Message", F("sansb", 19), y=y + 13, x0=L + bw + 6, x1=L + 2 * bw + 6)
    p.d.rounded_rectangle((R - 54, y, R, y + 46), radius=8, outline=K, width=3)
    _icon(p.d, "dots", R - 27, y + 23)
    y += 66
    # tab pill
    x = L
    for i, t in enumerate(["Posts", "About", "Photos", "Videos"]):
        f = F("sansb", 18)
        tw = p.tw(t, f)
        if i == 0:
            p.d.rounded_rectangle((x, y, x + tw + 28, y + 38), radius=19, fill=K)
            p.text(x + 14, y + 10, t, f, fill=P)
        else:
            p.text(x + 14, y + 10, t, f)
        x += tw + 40
    y += 56
    p.d.rectangle((0, y, W, y + 5), fill=K)
    y += 22
    # postingan
    pa = 54
    _put_avatar(p, c, L, y, pa)
    tx = L + pa + 12
    p.text(tx, y + 4, s["name"], F("sansb", 19))
    p.text(tx, y + 30, "Just now · ", F("sans", 16))
    _icon2(p.d, "globe", tx + p.tw("Just now · ", F("sans", 16)) + 9, y + 38, s=16)
    _icon(p.d, "dots", R - 6, y + 20)
    y += pa + 14
    post = c.caption or f"Kenangan dari {c.event}"
    y = _wrap_text(p, L, y, post, F("sans", 20), R - L, 28) + 10
    rects, bottom = _collage(c, 4, y, W - 8, "fb", gap=4)
    for i, (x, yy, w, h) in enumerate(rects):
        _photo_r(p, c, i, x, yy, w, h)
    y = bottom + 14
    p.d.ellipse((L, y, L + 26, y + 26), fill=K)
    _icon2(p.d, "like", L + 13, y + 13, s=14, w=2, fill=P)
    likes = rnd.randint(500, 10000)
    p.text(L + 34, y + 4, f"You and {_fmt_num(likes)} others", F("sans", 17))
    p.right(f"{rnd.randint(10, 400)} comments · {rnd.randint(5, 90)} shares", F("sans", 17), y + 4, x1=R)
    y += 38
    p.d.rectangle((L, y, R, y + 1), fill=K)
    y += 12
    cw = (R - L) / 3
    for i, (k, t) in enumerate((("like", "Like"), ("comment", "Comment"), ("share", "Share"))):
        f = F("sansb", 18)
        bw2 = 30 + p.tw(t, f)
        x0 = L + i * cw + (cw - bw2) / 2
        _icon2(p.d, k, x0 + 11, y + 12, s=22)
        p.text(x0 + 30, y + 3, t, f)
    y += 46
    return _phone_end(p, c, y)


def t_youtube(c):
    s = _social(c)
    rnd = s["rnd"]
    p = Paper(c.W)
    W, L, R = c.W, 26, c.W - 26
    y = 26
    _photo_r(p, c, c.n - 1, L, y, R - L, 120, r=16)
    y += 140
    av = 104
    _put_avatar(p, c, L, y, av)
    tx = L + av + 18
    ty = y + 4
    for line in p.wrap(s["name"], F("sansb", 28), R - tx)[:2]:
        p.text(tx, ty, line, F("sansb", 28))
        ty += 36
    p.text(tx, ty + 2, "@" + s["user"], F("sans", 18))
    subs, vids = rnd.randint(500, 10000), rnd.randint(12, 400)
    p.text(tx, ty + 30, f"{_num_short(subs)} subscribers · {vids} videos", F("sans", 18))
    y = max(y + av, ty + 56) + 16
    y = _wrap_text(p, L, y, s["bio"] + "  >", F("sans", 19), R - L, 27)
    p.text(L, y, s["web"], F("sansb", 18))
    y += 38
    p.d.rounded_rectangle((L, y, R, y + 50), radius=25, fill=K)
    p.center("Subscribe", F("sansb", 21), y=y + 14, x0=L, x1=R, fill=P)
    y += 72
    y = _tabs(p, y, ["Home", "Videos", "Shorts", "Playlists"], 1, size=18)
    y += 20

    def video(i, x, y, w, small=False):
        h = int(w * 9 / 16)
        _photo_r(p, c, i, x, y, w, h, r=12 if small else 16)
        dur = f"{rnd.randint(0, 12)}:{rnd.randint(0, 59):02d}"
        fd = F("monob", 14 if small else 16)
        dw = p.tw(dur, fd) + 12
        p.d.rounded_rectangle((x + w - dw - 8, y + h - 32, x + w - 8, y + h - 8), radius=5, fill=K)
        p.text(x + w - dw - 2, y + h - 26, dur, fd, fill=P)
        y += h + 10
        title = (c.caption if (i == 0 and c.caption) else f"Momen #{i + 1} di {c.event}")
        ft = F("sansb", 16 if small else 20)
        tx2 = x if small else x + 52
        if not small:
            _put_avatar(p, c, x, y, 40)
        y = _wrap_text(p, tx2, y, title, ft, x + w - tx2, 22 if small else 27, max_lines=2)
        views = _num_short(rnd.randint(500, 90000))
        meta = f"{views} views · {rnd.randint(1, 59)} min ago"
        y = _wrap_text(p, tx2, y + 2, meta, F("sans", 14 if small else 17), x + w - tx2, 20, max_lines=1)
        return y

    if c.n == 4:
        cw = (R - L - 16) // 2
        for row in range(2):
            ys = [video(row * 2 + k, L + k * (cw + 16), y, cw, small=True) for k in range(2)]
            y = max(ys) + 18
    else:
        for i in range(c.n):
            y = video(i, L, y, R - L) + 22
    return _phone_end(p, c, y)


# ================================================================ KALENDER

def t_kalender(c):
    """Kalender meja: foto di atas, kalender bulan berjalan di bawah, tanggal cetak dilingkari."""
    import calendar as _cal
    W = c.W
    p = Paper(W)
    d = p.d
    L, R = 30, W - 30
    # ring spiral
    y = 14
    n_ring = 9
    step = (R - L) / (n_ring - 1)
    for i in range(n_ring):
        cx = L + i * step
        d.rounded_rectangle((cx - 6, y, cx + 6, y + 34), radius=6, outline=K, width=3)
    y += 22
    top = y
    y += 30
    # foto
    rects, y = slots(c.layout, L + 14, y, R - L - 28, gap=12, solo_r=0.8, strip_r=0.62)
    put_photos(p, c, rects, border=2, frame_gap=5)
    y += 34
    # bulan & tahun
    mon, yr = month_name(c.now.month).upper(), str(c.now.year)
    fy = F("bebas", 72)
    room = (R - 14) - (L + 14) - p.tw(yr, fy) - 24
    ms = 72
    while p.tw(mon, F("bebas", ms)) > room and ms > 30:     # bulan panjang (NOVEMBER, SEPTEMBER) tidak menabrak tahun
        ms -= 2
    p.text(L + 14, y + (72 - ms) * 0.7, mon, F("bebas", ms))
    p.right(yr, fy, y, x1=R - 14)
    y += 74
    y = p.rule(3, x0=L + 14, x1=R - 14, y=y) + 14
    # kalender (minggu dimulai MINGGU)
    days = ["MIN", "SEN", "SEL", "RAB", "KAM", "JUM", "SAB"]
    gx0, gx1 = L + 14, R - 14
    cw = (gx1 - gx0) / 7
    for i, dn in enumerate(days):
        p.center(dn, F("monob" if i == 0 else "mono", 17), y=y, x0=gx0 + i * cw, x1=gx0 + (i + 1) * cw)
    y += 34
    weeks = _cal.Calendar(firstweekday=6).monthdayscalendar(c.now.year, c.now.month)
    rh = 52
    for week in weeks:
        for i, day in enumerate(week):
            if not day:
                continue
            x0 = gx0 + i * cw
            cx, cy = x0 + cw / 2, y + rh / 2 - 4
            f = F("sansb" if i == 0 else "sans", 24)
            if day == c.now.day:
                r = 22
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=K)
                p.center(str(day), F("sansb", 24), y=cy - 9, x0=x0, x1=x0 + cw, fill=P)
            else:
                p.center(str(day), f, y=cy - 9, x0=x0, x1=x0 + cw)
        y += rh
    y += 6
    y = p.rule(3, x0=L + 14, x1=R - 14, y=y) + 22
    # keterangan
    hari = day_name(c.now.weekday()).capitalize()
    p.y = y
    if c.caption:
        p.para_center(c.caption, F("hand", 44), max_w=R - L - 28, line_gap=6)
        p.y += 4
    p.para_center(c.event.upper(), F("black", 30), max_w=R - L - 28, line_gap=6)
    p.y = p.center(f"{hari}, {c.date_long} · {c.time}", F("mono", 16), y=p.y + 4) + 24
    # bingkai kalender
    d.rounded_rectangle((L, top, R, p.y), radius=18, outline=K, width=4)
    p.y += 24
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
        p.y += 6
    return p.finish(bottom_pad=30)


# ================================================================ TEMPLATE LUCU (ramalan, boarding, dst.)

RAMALAN = [
    "Hari ini senyummu jadi alasan orang lain ikut bahagia.",
    "Rezeki datang dari arah tak terduga. Mungkin dari doorprize.",
    "Seseorang diam-diam menyimpan fotomu. Itu kamu, barusan.",
    "Kesabaranmu akan segera dibalas dengan makanan enak.",
    "Bintangmu terang malam ini. Lampu booth-nya juga.",
    "Hal baik datang bertiga: kamu, foto ini, dan struknya.",
    "Jangan lupa minum air putih, lalu pose lagi.",
    "Liburan sudah memanggil. Jawab teleponnya.",
    "Kamu akan bertemu orang baru yang menyenangkan hari ini.",
    "Pose berikutnya akan jadi foto terbaikmu tahun ini.",
]
GELAR = [
    "CAKEP MAKSIMAL | tanpa filter, tanpa editan",
    "CANTIK 95% | 5% sisanya ketinggalan di rumah",
    "GANTENG 95% | 5% lagi masih loading",
    "JELEK 3% | 97% sisanya kece parah",
    "AURA +1000 | terdeteksi dari jarak 5 meter",
    "MAIN CHARACTER | yang lain cuma figuran",
    "SPEK IDAMAN MERTUA | sopan, wangi, fotogenik",
    "BUKAN KALENG-KALENG | kualitas ekspor",
    "SLAY TOTAL | no debat",
    "GLOW UP BERHASIL | versi terbaik hari ini",
    "SENYUM 100% ORI | bukan KW",
    "VIBES JUARA | satu ruangan ikut bahagia",
    "PALING FOTOGENIK | kamera pun naksir",
    "KEREN TAPI SANTUY | low effort, high result",
]


def split_title(t):
    """'GELAR | keterangan' -> ('GELAR', 'keterangan')."""
    a, _, b = (t or "").partition("|")
    return a.strip(), b.strip()
OBAT = [
    ("Senyum lebar", "3x sehari sesudah makan"), ("Tertawa lepas", "sesuai kebutuhan"),
    ("Foto bareng teman", "min. 1x per acara"), ("Pelukan hangat", "2x sehari"),
    ("Liburan", "1x sebulan, jangan ditunda"), ("Air putih", "8 gelas sehari"),
    ("Tidur cukup", "tiap malam"), ("Dengar lagu favorit", "sebelum tidur"),
]
KESIMPULAN = ["Sangat cocok. Segera foto lagi.", "Cocok banget, tinggal tentukan tanggal.",
              "Kompak! Pertahankan.", "Chemistry di atas rata-rata.", "Satu frekuensi. Langka!"]
DIALOG = ["Eh, kameranya udah nyala?", "Senyum! Satu, dua...", "Ini dicetak di struk?!",
          "Pose andalan, go!", "Satu lagi, satu lagi!", "Siapa yang kedip?", "Fix ini masuk feed.",
          "Kok aku paling kece?", "Gaya bebas!", "Jangan lupa bahagia.", "Mana fotografernya?",
          "Cekrek!"]


def _rnd(c, salt=""):
    return random.Random(f"{salt}-{c.no}-{c.now.timestamp()}")


def _bar(p, x, y, w, h, pct):
    p.d.rectangle((x, y, x + w, y + h), outline=K, width=2)
    p.d.rectangle((x + 3, y + 3, x + 3 + int((w - 6) * pct / 100), y + h - 3), fill=K)


def _heart(d, cx, cy, s, fill=K):
    r = s / 4
    d.ellipse((cx - 2 * r, cy - r, cx, cy + r), fill=fill)
    d.ellipse((cx, cy - r, cx + 2 * r, cy + r), fill=fill)
    d.polygon([(cx - 2 * r + 1, cy + 2), (cx, cy + s / 1.6), (cx + 2 * r - 1, cy + 2)], fill=fill)


def _stamp(p, cx, cy, r, text, sub=""):
    d = p.d
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=K, width=5)
    d.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), outline=K, width=2)
    text, sub = tr(text), tr(sub)
    lay = Image.new("L", (2 * r, 2 * r), 0)
    ld = ImageDraw.Draw(lay)
    size = int(r * 0.55)
    f = F("bebas", size)
    while ld.textlength(text, font=f) > r * 1.5 and size > 12:   # teks panjang (mis. OFFICIAL) tetap muat
        size -= 2
        f = F("bebas", size)
    tw = ld.textlength(text, font=f)
    bb = f.getbbox(text)
    ld.text((r - tw / 2, r - (bb[3] - bb[1]) / 2 - bb[1] - (8 if sub else 0)), text, font=f, fill=255)
    if sub:
        fs = F("monob", int(r * 0.17))
        sw = ld.textlength(sub, font=fs)
        ld.text((r - sw / 2, r + r * 0.28), sub, font=fs, fill=255)
    lay = lay.rotate(-14, resample=Image.BICUBIC)
    p.img.paste(K, (int(cx - r), int(cy - r)), lay.point(lambda v: 255 if v > 110 else 0))


def _scribble(p, x, y, w, seed):
    r = random.Random(seed)
    pts = [(x + i * w / 14, y + r.randint(-14, 10)) for i in range(15)]
    p.d.line(pts, fill=K, width=3, joint="curve")


def t_ramalan(c):
    rnd = _rnd(c, "ramalan")
    p = Paper(c.W)
    W, L, R = c.W, 30, c.W - 30
    p.y = 26
    for x in (L + 20, R - 20):
        p.diamond(x, p.y + 30, 12)
    p.y = p.center("RAMALAN", F("black", 54)) + 8
    p.y = p.center("HARI INI · " + c.date_num, F("mono", 17), spacing=3) + 20
    p.y = p.dots(r=2, step=12, x0=L, x1=R) + 22
    rects, p.y = slots(c.layout, L, p.y, R - L, gap=12)
    put_photos(p, c, rects, border=3, frame_gap=4)
    p.y += 30
    # bola kristal
    cx = W / 2
    p.d.ellipse((cx - 40, p.y, cx + 40, p.y + 80), outline=K, width=4)
    p.d.arc((cx - 26, p.y + 12, cx + 6, p.y + 44), 180, 270, fill=K, width=4)
    p.d.polygon([(cx - 34, p.y + 98), (cx + 34, p.y + 98), (cx + 22, p.y + 74), (cx - 22, p.y + 74)], fill=K)
    p.y += 116
    p.para_center("“" + tr(rnd.choice(RAMALAN)) + "”", F("serifb", 26), max_w=R - L, line_gap=8)
    p.y += 16
    f = F("monob", 18)
    for lab in ["REZEKI", "JODOH", "KARIER", "MOOD"]:
        v = rnd.randint(62, 100)
        p.text(L, p.y + 2, lab, f)
        _bar(p, L + 130, p.y, R - L - 130 - 70, 24, v)
        p.right(f"{v}%", f, p.y + 2, x1=R)
        p.y += 38
    p.y += 10
    nums = sorted(rnd.sample(range(1, 50), 3))
    p.y = p.center("Angka keberuntungan: " + " · ".join(map(str, nums)), F("sans", 19)) + 10
    p.y = p.center("Warna keberuntungan: hitam (kata printer)", F("sans", 19)) + 18
    if c.caption:
        p.para_center(c.caption, F("hand", 40), max_w=R - L)
    p.y = p.dots(r=2, step=12, x0=L, x1=R, y=p.y + 6) + 18
    p.y = p.center(c.event.upper(), F("monob", 18)) + 20
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
    return p.finish()


def _plane(d, cx, cy, s, fill=P):
    d.polygon([(cx - s, cy), (cx + s, cy - 3), (cx + s + 6, cy), (cx + s, cy + 3)], fill=fill)
    d.polygon([(cx - 4, cy), (cx + 6, cy - s * 0.9), (cx + 12, cy - s * 0.9), (cx + 8, cy)], fill=fill)
    d.polygon([(cx - 4, cy), (cx + 6, cy + s * 0.9), (cx + 12, cy + s * 0.9), (cx + 8, cy)], fill=fill)
    d.polygon([(cx - s, cy), (cx - s - 4, cy - 10), (cx - s + 6, cy - 10), (cx - s + 8, cy)], fill=fill)


def t_boarding(c):
    rnd = _rnd(c, "board")
    p = Paper(c.W)
    W, L, R = c.W, 24, c.W - 24
    top = 12
    p.d.rounded_rectangle((8, top, W - 9, top + 84), radius=18, fill=K, corners=(True, True, False, False))
    p.text(L + 10, top + 20, "BOARDING PASS", F("bebas", 54), fill=P)
    _plane(p.d, R - 40, top + 42, 26)
    y = top + 106
    p.text(L + 6, y, "FROM", F("mono", 14))
    p.right("TO", F("mono", 14), y, x1=R - 6)
    y += 22
    o = c.opts
    fcode = (o.get("board_from_code") or "SNI").upper()[:4]
    tcode = (o.get("board_to_code") or "BHG").upper()[:4]
    p.text(L + 6, y, fcode, F("bebas", 84))
    p.right(tcode, F("bebas", 84), y, x1=R - 6)
    _plane(p.d, W / 2, y + 40, 22, fill=K)
    p.dashed(h=2, dash=6, gap=6, x0=L + 150, x1=W / 2 - 36, y=y + 40)
    p.dashed(h=2, dash=6, gap=6, x0=W / 2 + 40, x1=R - 150, y=y + 40)
    y += 86
    p.text(L + 6, y, (o.get("board_from") or "Sini")[:22], F("sans", 17))
    p.right((o.get("board_to") or "Bahagia")[:22], F("sans", 17), y, x1=R - 6)
    y += 36
    name = (c.caption or "TAMU ISTIMEWA").upper()
    p.text(L + 6, y, "PASSENGER", F("mono", 14))
    y += 22
    y += p.text(L + 6, y, name[:28], F("sansb", 24)) + 20
    seat = f"{rnd.randint(1, 30)}{rnd.choice('ABCDEF')}"
    gate = f"{rnd.choice('ABC')}{rnd.randint(1, 12)}"
    cells = [("FLIGHT", f"PB{c.no}"), ("GATE", gate), ("SEAT", seat), ("BOARDING", c.time)]
    cw = (R - L) / 4
    for i, (k, v) in enumerate(cells):
        x = L + i * cw + 6
        p.text(x, y, k, F("mono", 13))
        p.text(x, y + 20, v, F("bebas", 38))
    y += 76
    p.text(L + 6, y, "DATE", F("mono", 13))
    p.text(L + 6 + 2 * cw, y, "CLASS", F("mono", 13))
    p.text(L + 6, y + 20, c.now.strftime("%d %b %Y").upper(), F("bebas", 34))
    p.text(L + 6 + 2 * cw, y + 20, "FIRST CLASS", F("bebas", 34))
    y += 74
    rects, y = slots(c.layout, L + 6, y, R - L - 12, gap=10)
    put_photos(p, c, rects, border=3)
    y += 22
    p.d.rounded_rectangle((8, top, W - 9, y), radius=18, outline=K, width=4)
    # sobekan
    y += 22
    p.dots(r=3, step=13, y=y)
    y += 18
    p.y = p.center("SOBEK DI SINI", F("mono", 13), y=y, spacing=4) + 16
    st = p.y
    p.y += 18
    p.text(L + 10, p.y, f"PB{c.no}", F("bebas", 40))
    p.right(f"SEAT {seat} · GATE {gate}", F("monob", 18), p.y + 12, x1=R - 10)
    p.y += 54
    bw = R - L - 20 - (150 if c.qr is not None else 0)
    p.barcode(L + 10, p.y, bw, 90, seed=c.no)
    if c.qr is not None:
        p.paste(qr_fit(c.qr, 130), R - 10 - 130, p.y - 10)
    p.y += 124
    p.d.rounded_rectangle((8, st, W - 9, p.y), radius=14, outline=K, width=4)
    p.y += 6
    return p.finish()


def t_sertifikat(c):
    with no_translate():
        rnd = _rnd(c, "cert")
        p = Paper(c.W)
        W, L, R = c.W, 50, c.W - 50
        p.y = 52
        p.y = p.center("SERTIFIKAT", F("serifk", 54)) + 10
        p.y = p.center(f"No. {c.no}/PB/{c.now.year}", F("mono", 16)) + 18
        p.y = p.ornament(p.y) + 22
        p.y = p.center("Dengan ini menyatakan bahwa", F("serif", 21)) + 20
        rects, p.y = slots(c.layout, L, p.y, R - L, gap=12)
        put_photos(p, c, rects, border=2, frame_gap=5)
        p.y += 26
        who = c.caption or "Pemegang sertifikat ini"
        p.para_center(who, F("hand", 44), max_w=R - L)
        p.y += 6
        p.y = p.center("telah resmi dinyatakan sebagai", F("serif", 21)) + 16
        titles = [t for t in (c.opts.get("cert_titles") or GELAR) if t.strip()] or GELAR
        title, sub = split_title(c.opts.get("cert_title") or rnd.choice(titles))
        p.para_center(title.upper(), F("black", 40), max_w=R - L, line_gap=6)
        if sub:
            p.y += 2
            p.para_center(f"({sub})", F("hand", 32), max_w=R - L, line_gap=4)
        p.y += 10
        p.y = p.center(f"Ditetapkan di {c.event}", F("serif", 19)) + 6
        p.y = p.center(c.date_long, F("serif", 19)) + 34
        sy = p.y
        _stamp(p, L + 80, sy + 70, 66, "RESMI", "PHOTOBOOTH")
        _scribble(p, R - 210, sy + 60, 200, c.no)
        p.d.rectangle((R - 220, sy + 92, R, sy + 93), fill=K)
        p.center("Ketua Panitia Senyum", F("serif", 16), y=sy + 102, x0=R - 220, x1=R)
        p.y = sy + 160
        p.d.rectangle((6, 14, W - 7, p.y), outline=K, width=4)
        p.d.rectangle((18, 26, W - 19, p.y - 12), outline=K, width=1)
        for cx, cy in [(18, 26), (W - 19, 26), (18, p.y - 12), (W - 19, p.y - 12)]:
            p.diamond(cx, cy, 9)
            p.diamond(cx, cy, 4, fill=P)
        p.y += 24
        if c.qr is not None:
            p.qr_row(c, size=130, x=M)
        return p.finish()


def t_resep(c):
    rnd = _rnd(c, "resep")
    p = Paper(c.W)
    W, L, R = c.W, 30, c.W - 30
    p.y = 26
    p.text(L, p.y, "dr. Booth, Sp.S", F("serifb", 34))
    p.y += 44
    p.text(L, p.y, "Spesialis Senyum", F("serif", 20))
    p.right(f"SIP {c.no}/PB/{c.now.year}", F("mono", 15), p.y + 4, x1=R)
    p.y += 30
    p.text(L, p.y, f"Praktik: {c.event}"[:44], F("sans", 17))
    p.y += 30
    p.y = p.rule(4, x0=L, x1=R) + 3
    p.y = p.rule(1, x0=L, x1=R) + 18
    f = F("sans", 19)
    p.text(L, p.y, "Pro  :", f)
    p.text(L + 70, p.y - 6, c.caption or "Tamu istimewa", F("hand", 32))
    p.y += 36
    p.text(L, p.y, "Tgl  :", f)
    p.text(L + 70, p.y, f"{c.date_long}, {c.time}", f)
    p.y += 40
    p.text(L, p.y, "R/", F("serifk", 64))
    p.y += 80
    rects, p.y = slots(c.layout, L, p.y, R - L, gap=10)
    put_photos(p, c, rects, border=2, frame_gap=4)
    p.y += 26
    for nama, aturan in rnd.sample(OBAT, 3):
        p.text(L, p.y, "R/", F("serifb", 26))
        p.text(L + 50, p.y - 6, nama, F("hand", 36))
        p.y += 40
        p.text(L + 50, p.y - 4, "S " + aturan, F("hand", 30))
        p.d.line((R - 60, p.y + 4, R - 40, p.y + 18, R - 10, p.y - 14), fill=K, width=3)
        p.y += 44
    p.y += 6
    _scribble(p, R - 200, p.y + 36, 190, c.no)
    p.y += 60
    p.d.rectangle((R - 210, p.y, R, p.y + 1), fill=K)
    p.center("dr. Booth", F("serif", 16), y=p.y + 8, x0=R - 210, x1=R)
    p.y += 44
    p.y = p.dashed(h=2, x0=L, x1=R) + 16
    p.y = p.center("Obat tidak perlu ditebus. Gratis.", F("monob", 17)) + 20
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
    return p.finish()


def t_cocok(c):
    rnd = _rnd(c, "cocok")
    p = Paper(c.W)
    W, L, R = c.W, 30, c.W - 30
    p.y = 26
    p.y = p.center("LAB PHOTOBOOTH", F("monob", 18), spacing=3) + 10
    p.y = p.center("HASIL TES KECOCOKAN", F("black", 36)) + 10
    f = F("mono", 15)
    p.text(L, p.y, f"No. Sampel : {c.no}", f)
    p.right(c.date_num + " " + c.time, f, p.y, x1=R)
    p.y += 26
    p.y = p.rule(3, x0=L, x1=R) + 20
    rects, p.y = slots(c.layout, L, p.y, R - L, gap=10)
    put_photos(p, c, rects, border=2)
    p.y += 26
    score = rnd.randint(86, 100)
    sw = p.tw(f"{score}%", F("bebas", 150))
    x0 = (W - sw - 90) / 2
    _heart(p.d, x0 + 34, p.y + 50, 74)
    p.text(x0 + 90, p.y, f"{score}%", F("bebas", 150))
    p.y += 160
    p.y = p.center("TINGKAT KECOCOKAN", F("monob", 18), spacing=3) + 22
    p.text(L, p.y, "PEMERIKSAAN", F("monob", 15))
    p.right("HASIL", F("monob", 15), p.y, x1=R)
    p.y += 24
    p.y = p.rule(1, x0=L, x1=R) + 12
    for lab in ["Chemistry", "Selera humor", "Selera makan", "Kekompakan pose", "Level bucin"]:
        v = rnd.randint(70, 100)
        p.text(L, p.y + 2, lab, F("sans", 18))
        _bar(p, L + 200, p.y, R - L - 200 - 64, 22, v)
        p.right(f"{v}%", F("monob", 17), p.y + 2, x1=R)
        p.y += 34
    p.y += 6
    p.y = p.rule(1, x0=L, x1=R) + 16
    p.text(L, p.y, "KESIMPULAN:", F("monob", 16))
    p.y += 28
    p.para_center(c.caption or rnd.choice(KESIMPULAN), F("hand", 42), max_w=R - L)
    p.y += 8
    p.y = p.center("Diperiksa oleh: Lab Photobooth " + c.event, F("sans", 15)) + 20
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
    return p.finish()


def t_kartupos(c):
    p = Paper(c.W)
    W, L, R = c.W, 26, c.W - 26
    p.y = 26
    p.text(L, p.y + 6, "KARTU POS", F("bebas", 58))
    p.text(L, p.y + 68, "POSTCARD", F("mono", 16), spacing=4)
    # prangko
    sx, sy, sw, sh = R - 110, p.y, 110, 132
    m = _mask(sw, sh, shape_stamp)
    p.img.paste(K, (sx, sy, sx + sw, sy + sh), m)
    inner = _mask(sw - 16, sh - 16, shape_rect)
    p.img.paste(c.ph(0, sw - 16, sh - 16), (sx + 8, sy + 8), inner)
    # cap pos
    cx, cy = sx - 66, sy + 82
    for k in range(3):
        yy = cy - 14 + k * 14
        p.d.arc((cx - 130, yy - 6, cx - 90, yy + 6), 180, 360, fill=K, width=2)
        p.d.arc((cx - 90, yy - 6, cx - 50, yy + 6), 0, 180, fill=K, width=2)
    p.d.ellipse((cx - 50, cy - 50, cx + 50, cy + 50), fill=P, outline=K, width=3)
    p.center(c.now.strftime("%d %b").upper(), F("monob", 15), y=cy - 18, x0=cx - 50, x1=cx + 50)
    p.center(str(c.now.year), F("monob", 15), y=cy + 4, x0=cx - 50, x1=cx + 50)
    p.y = sy + sh + 24
    rects, p.y = slots(c.layout, L, p.y, R - L, gap=10)
    put_photos(p, c, rects, border=3)
    p.y += 28
    f = F("sans", 19)
    p.text(L, p.y, "Untuk:", f)
    p.dashed(h=2, dash=4, gap=5, x0=L + 76, x1=R, y=p.y + 22)
    p.y += 46
    p.text(L, p.y, "Pesan:", f)
    p.y += 10
    if c.caption:
        p.text(L + 76, p.y - 14, c.caption, F("hand", 34))
    for k in range(5):
        p.y += 44
        p.dashed(h=2, dash=4, gap=5, x0=L, x1=R, y=p.y)
    p.y += 30
    p.text(L, p.y, "Dari:", f)
    p.text(L + 76, p.y - 8, c.event, F("hand", 34))
    p.y += 50
    p.d.rectangle((8, 12, W - 9, p.y), outline=K, width=3)
    p.y += 22
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
    return p.finish()


def _balloon(p, x, y, maxw, text, tail_x, tail_down=True):
    f = F("sansb", 20)
    lines = p.wrap(text, f, maxw - 36)
    lh = 26
    tw = max(p.tw(ln, f) for ln in lines)
    bw, bh = tw + 40, len(lines) * lh + 26
    d = p.d
    d.ellipse((x - 3, y - 3, x + bw + 3, y + bh + 3), fill=K)
    if tail_down:
        d.polygon([(tail_x - 12, y + bh - 10), (tail_x + 12, y + bh - 10), (tail_x - 4, y + bh + 26)], fill=K)
        d.polygon([(tail_x - 8, y + bh - 12), (tail_x + 7, y + bh - 12), (tail_x - 3, y + bh + 18)], fill=P)
    d.ellipse((x, y, x + bw, y + bh), fill=P)
    ty = y + 13
    for ln in lines:
        p.center(ln, f, y=ty, x0=x, x1=x + bw)
        ty += lh


def t_komik(c):
    rnd = _rnd(c, "komik")
    p = Paper(c.W)
    W, L, R = c.W, 16, c.W - 16
    p.y = 18
    p.y = p.center(c.event.upper(), F("black", 34)) + 4
    p.y = p.center(f"EDISI #{c.no} · {c.date_num}", F("monob", 15), spacing=2) + 16
    gap = 14
    if c.layout == "grid":
        s = (R - L - gap) // 2
        rects = [(L + (i % 2) * (s + gap), p.y + (i // 2) * (s + gap), s, s) for i in range(4)]
    else:
        ratio = {1: 1.0, 2: 0.8, 3: 0.7}[c.n]
        h = int((R - L) * ratio)
        rects = [(L, p.y + i * (h + gap), R - L, h) for i in range(c.n)]
    lines = rnd.sample(DIALOG, len(rects))
    small = c.layout == "grid"
    for i, (x, y, w, h) in enumerate(rects):
        p.paste(c.ph(i, w, h), x, y)
        p.d.rectangle((x - 4, y - 4, x + w + 3, y + h + 3), outline=K, width=5)
        if i == 0:
            cap = f"Suatu hari di {c.event}..."
            fc = F("monob", 14 if small else 16)
            cl = p.wrap(cap, fc, w * 0.62)
            bh = len(cl) * 22 + 14
            bw = max(p.tw(t, fc) for t in cl) + 20
            p.d.rectangle((x, y, x + bw, y + bh), fill=P, outline=K, width=3)
            ty = y + 8
            for t in cl:
                p.text(x + 10, ty, t, fc)
                ty += 22
            by = y + bh + 10
        else:
            by = y + 12
        text = c.caption if (i == len(rects) - 1 and c.caption) else lines[i]
        mw = int(w * (0.85 if small else 0.62))
        bx = x + (w - mw - 12 if i % 2 else 12)
        _balloon(p, bx, by, mw, text, bx + mw // 3)
    p.y = max(r[1] + r[3] for r in rects) + 16
    fb = F("bebas", 40)
    tw = p.tw("TAMAT", fb) + 30
    p.d.rectangle((R - tw, p.y, R, p.y + 46), fill=K)
    p.text(R - tw + 15, p.y + 6, "TAMAT", fb, fill=P)
    p.y += 66
    if c.qr is not None:
        p.qr_row(c, size=130, x=M)
    return p.finish()



# ============================================ TEMPLATE BARU (otentik/unik)

def _star(d,cx,cy,r,fill=0):
    pts=[]
    for i in range(10):
        a=-math.pi/2+i*math.pi/5
        rr=r if i%2==0 else r*0.42
        pts.append((cx+rr*math.cos(a),cy+rr*math.sin(a)))
    d.polygon(pts,fill=fill)

# 1 ---------------- Music / Playlist Receipt ----------------
def t_musik(c):
    p=Paper(c.W); W=c.W; m=36
    p.y=30
    words=c.event.upper().split()
    if len(words)>=2:
        p.y=p.center(words[0], F("black",62))+2
        p.y=p.center(" ".join(words[1:]).lower(), F("serifk",50))+16
    else:
        p.y=p.center(c.event.upper(), F("black",56))+16
    p.y=p.center("TRACK ORDER", F("monob",20), spacing=6)+8
    p.y=p.center(c.date_long, F("mono",18))+16
    p.y=p.rule(2,x0=m,x1=W-m)+16
    f=F("mono",22)
    tracks=[("01  GOLDEN HOUR","03:21"),("02  BEST DAY EVER","04:02"),
            ("03  STAY LIKE THIS","02:48"),("04  ONE MORE POSE","03:33")]
    for a,b in tracks[:max(2,c.n)+1]:
        p.text(m,p.y,a,f); p.right(b,f,p.y,x1=W-m); p.y+=34
    p.y+=4
    p.y=p.dashed(h=2,x0=m,x1=W-m)+10
    fb=F("monob",24)
    p.text(m,p.y,"TOTAL",fb); p.right("FOREVER",fb,p.y,x1=W-m); p.y+=42
    p.y=p.rule(2,x0=m,x1=W-m)+20
    rects,p.y=slots(c.layout,m,p.y,W-2*m,gap=12,solo_r=1.15,duo_r=0.95,strip_r=1.1,grid_r=1.0)
    put_photos(p,c,rects)
    p.y+=22
    p.para_center("Printed like a receipt, kept like a memory.", F("serif",24), max_w=W-2*m, line_gap=6)
    p.y+=16
    p.qr_row(c, size=150, x=(W-150)//2) if c.qr is not None else None
    p.y+=6
    p.y=p.center("THE ART OF THE MOMENT", F("monob",18), spacing=4)+12
    return p.finish()

# 2 ---------------- Theater Ticket Photostrip ----------------
def t_teater(c):
    p=Paper(c.W); W=c.W; m=10; m2=34
    p.y=16; top=p.y; bandh=64
    p.d.rectangle((m,p.y,W-m-1,p.y+bandh),fill=0)
    p.center("THEATER TICKET", F("bebas",52), y=p.y+9, fill=255)
    p.y+=bandh+18
    _star(p.d,m2+4,p.y+6,13); _star(p.d,W-m2-4,p.y+6,13)
    p.y=p.center("ADMIT ONE", F("black",30))+10
    p.y=p.center(c.event.upper(), F("serifb",36))+6
    if c.caption: p.y=p.center(c.caption, F("hand",40))+6
    p.y+=6
    p.y=p.dots(r=2,step=10,x0=m2,x1=W-m2)+16
    cols=[("ROW","A"),("SEAT",c.no[-2:]),("DATE",c.now.strftime("%d %b").upper())]
    bw=(W-2*m2-2*10)/3
    for i,(lab,val) in enumerate(cols):
        x=m2+i*(bw+10)
        p.text(x,p.y,lab,F("mono",15)); p.text(x,p.y+22,val,F("bebas",34))
    p.y+=66
    rects,p.y=slots(c.layout,m2,p.y,W-2*m2,gap=12,solo_r=1.2,duo_r=0.9,strip_r=1.1,grid_r=1.0)
    put_photos(p,c,rects,border=3)
    p.y+=20
    p.y=p.center("MEMORIES THEATER", F("monob",18), spacing=3)+16
    p.d.rectangle((m,top,W-m-1,p.y),outline=0,width=4)
    p.y+=22; p.dots(r=3,step=13,y=p.y); p.y+=18
    stub_top=p.y; p.y+=16
    p.text(m2,p.y,"STUB", F("bebas",40)); p.right(f"NO.{c.no}", F("monob",18), p.y+12, x1=W-m2)
    p.y+=58
    p.barcode(m2,p.y,W-2*m2,80,seed=c.no); p.y+=96
    p.d.rectangle((m,stub_top,W-m-1,p.y),outline=0,width=4)
    p.y+=10
    return p.finish()

# 3 ---------------- Now Playing (music player) ----------------
def t_nowplaying(c):
    p=Paper(c.W); W=c.W; m=40
    p.y=30
    p.y=p.center("NOW PLAYING", F("monob",18), spacing=6)+20
    rects,p.y=slots(c.layout,m,p.y,W-2*m,gap=12,solo_r=1.0,duo_r=0.85,strip_r=0.9,grid_r=1.0)
    put_photos(p,c,rects,border=0)
    p.y+=26
    p.y=p.center(c.event.upper(), F("black",40))+6
    p.y=p.center(c.caption or "feat. good vibes", F("serif",24))+22
    # progress bar
    bx0,bx1=m,W-m; by=p.y; p.d.rectangle((bx0,by,bx1,by+4),fill=0)
    knob=bx0+int((bx1-bx0)*0.42); p.d.ellipse((knob-8,by-6,knob+8,by+10),fill=0)
    p.y+=20
    f=F("mono",18); p.text(bx0,p.y,"1:27",f); p.right("3:45",f,p.y,x1=bx1); p.y+=40
    # transport controls
    cy=p.y+10; cx=W//2
    d=p.d
    d.polygon([(cx-90,cy-14),(cx-108,cy),(cx-90,cy+14)],fill=0); d.polygon([(cx-74,cy-14),(cx-92,cy),(cx-74,cy+14)],fill=0)
    d.ellipse((cx-26,cy-26,cx+26,cy+26),fill=0); d.polygon([(cx-8,cy-13),(cx+15,cy),(cx-8,cy+13)],fill=255)
    d.polygon([(cx+74,cy-14),(cx+92,cy),(cx+74,cy+14)],fill=0); d.polygon([(cx+90,cy-14),(cx+108,cy),(cx+90,cy+14)],fill=0)
    p.y+=64
    p.qr_row(c, size=130, x=(W-130)//2) if c.qr is not None else None
    p.y+=6
    p.y=p.center(c.footer, F("monob",18), spacing=3)+12
    return p.finish()

# 4 ---------------- Concert / Festival Ticket ----------------
def t_konser(c):
    p=Paper(c.W); W=c.W; m=10; m2=34
    p.y=16; top=p.y
    p.y=p.center("LIVE IN CONCERT", F("monob",18), spacing=4)+12
    p.para_center(c.event.upper(), F("black",46), max_w=W-2*m2, line_gap=4); p.y+=6
    p.y=p.center(c.date_long+"  ·  GATE 7PM", F("mono",18))+16
    p.y=p.dashed(h=2,x0=m2,x1=W-m2)+14
    p.y=p.center("LINE UP", F("monob",17), spacing=5)+12
    for name in ["THE MIDNIGHTS","GOLDEN HOUR","PAPER PLANES","and more..."]:
        p.y=p.center(name, F("serifb",26))+8
    p.y+=12
    p.y=p.dashed(h=2,x0=m2,x1=W-m2)+16
    rects,p.y=slots(c.layout,m2,p.y,W-2*m2,gap=12,solo_r=1.15,duo_r=0.9,strip_r=1.05,grid_r=1.0)
    put_photos(p,c,rects,border=3)
    p.y+=20
    cols=[("SEC","GA"),("ROW","--"),("SEAT",c.no[-2:])]
    bw=(W-2*m2-2*10)/3
    for i,(lab,val) in enumerate(cols):
        x=m2+i*(bw+10); p.d.rectangle((x,p.y,x+bw,p.y+72),outline=0,width=2)
        p.text(x+10,p.y+10,lab,F("mono",14)); p.text(x+10,p.y+32,val,F("bebas",34))
    p.y+=72+20
    p.d.rectangle((m,top,W-m-1,p.y),outline=0,width=4)
    p.y+=22; p.dots(r=3,step=13,y=p.y); p.y+=18
    p.barcode(m2,p.y,W-2*m2,80,seed=c.no); p.y+=94
    p.y=p.center(f"ADMIT ONE · NO.{c.no}", F("mono",16), spacing=2)+12
    return p.finish()

# 5 ---------------- Chat / iMessage ----------------
def t_chat(c):
    p=Paper(c.W); W=c.W; m=28
    p.y=22
    # header
    p.d.ellipse((m,p.y,m+46,p.y+46),outline=0,width=3)
    p.text(m+60,p.y+2,c.event.title(),F("sansb",26)); p.text(m+60,p.y+30,"online now",F("sans",16))
    p.y+=64; p.y=p.rule(2,x0=0,x1=W)+22
    def bubble(text, right=False, f=None):
        f=f or F("sans",22)
        lines=p.wrap(text,f,W*0.6)
        bw=max(p.tw(l,f) for l in lines)+36; bh=len(lines)*32+24
        if right: x0=W-m-bw
        else: x0=m
        p.d.rounded_rectangle((x0,p.y,x0+bw,p.y+bh),radius=22,outline=0,width=3)
        ty=p.y+12
        for l in lines: p.text(x0+18,ty,l,f); ty+=32
        p.y+=bh+16
    bubble("Say cheese! ready?? 📸")
    bubble("always ready 😎", right=True)
    # photo as sent image
    rects,p.y=slots(c.layout,W-m-300 if c.layout in ("solo",) else m,p.y,300 if c.layout=="solo" else W-2*m,gap=10,solo_r=1.0,duo_r=1.0,strip_r=1.0,grid_r=1.0)
    put_photos(p,c,rects,border=3)
    p.y+=16
    bubble("okay this is THE one 🤍", right=True)
    bubble("framing it forever")
    p.y+=6
    p.y=p.center("Delivered", F("sans",16))+16
    p.qr_row(c, size=120, x=(W-120)//2) if c.qr is not None else None
    p.y+=4
    return p.finish()

# 6 ---------------- Vintage ID / Member Card ----------------
def t_idcard(c):
    p=Paper(c.W); W=c.W; m=24
    p.y=22; top=p.y
    p.d.rectangle((m,p.y,W-m-1,p.y+58),fill=0)
    p.center("MEMBER CARD", F("bebas",46), y=p.y+8, fill=255); p.y+=58+8
    p.center(c.event.upper(), F("monob",18), y=p.y, spacing=3); p.y+=34
    p.y=p.rule(2,x0=m,x1=W-m)+18
    # photo left, details right
    pw=190; ph=int(pw*1.25)
    p.paste(c.ph(0,pw,ph),m,p.y); p.d.rectangle((m,p.y,m+pw,p.y+ph),outline=0,width=3)
    dx=m+pw+26; f=F("mono",18); fy=p.y+4
    for lab,val in [("NAME",(c.caption or "GUEST").upper()),("ID NO",c.no),
                    ("ISSUED",c.now.strftime("%d %b %Y")),("EXP","NEVER"),("TYPE","VIP")]:
        p.text(dx,fy,lab,F("mono",14)); p.text(dx,fy+20,val,F("sansb",22)); fy+=58
    p.y+=ph+20
    p.y=p.dashed(h=2,x0=m,x1=W-m)+14
    # extra strip if more photos
    if c.n>1:
        rects,p.y=slots("strip" if c.n>=3 else "duo", m, p.y, W-2*m, gap=10,strip_r=0.85,duo_r=0.8)
        put_photos(p,c,rects,border=2); p.y+=16
    p.text(m,p.y,"SIGNATURE",F("mono",14)); p.d.line((m+120,p.y+20,W-m,p.y+20),fill=0,width=2); p.y+=40
    p.barcode(m,p.y,W-2*m,64,seed=c.no); p.y+=78
    p.d.rectangle((m-4,top-4,W-m+3,p.y+4),outline=0,width=2)
    p.y+=16
    return p.finish()

# 7 ---------------- Movie Poster ----------------
def t_poster(c):
    p=Paper(c.W); W=c.W; m=30
    p.y=24
    p.y=p.center("NOW SHOWING", F("monob",18), spacing=6)+16
    rects,p.y=slots(c.layout,m,p.y,W-2*m,gap=12,solo_r=1.3,duo_r=1.0,strip_r=1.05,grid_r=1.0)
    put_photos(p,c,rects,border=0)
    p.y+=24
    p.para_center(c.event.upper(), F("serifk",58), max_w=W-2*m, line_gap=2); p.y+=10
    p.y=p.center("— a film about good friends —", F("serif",22))+16
    p.y=p.center("STARRING", F("monob",15), spacing=5)+10
    p.y=p.center((c.caption or "YOU & THE GANG").upper(), F("sansb",24))+18
    for _ in range(1):
        cx=W//2
        for k in range(5): _star(p.d,cx-80+k*40,p.y+8,12)
    p.y+=30
    p.y=p.dashed(h=2,x0=m,x1=W-m)+14
    f=F("mono",18)
    p.text(m,p.y,"RUNTIME  "+str(90+int(c.no[-2:] or 0))+" MIN",f)
    p.right("RATED  G", f, p.y, x1=W-m); p.y+=30
    p.text(m,p.y,"RELEASE  "+c.now.strftime("%d.%m.%Y"),f)
    p.right("SCREEN 1", f, p.y, x1=W-m); p.y+=36
    p.qr_row(c, size=130, x=(W-130)//2) if c.qr is not None else None
    p.y+=4
    p.y=p.center(c.footer, F("monob",18), spacing=3)+12
    return p.finish()

# 8 ---------------- Coffee Shop Receipt ----------------
def t_kopi(c):
    p=Paper(c.W); W=c.W; m=36
    p.y=28
    # cup icon
    cx=W//2
    p.d.rectangle((cx-26,p.y,cx+22,p.y+34),outline=0,width=3)
    p.d.arc((cx+18,p.y+4,cx+40,p.y+26),-90,90,fill=0,width=3)
    p.d.line((cx-20,p.y-8,cx-16,p.y-16),fill=0,width=2); p.d.line((cx,p.y-8,cx+4,p.y-16),fill=0,width=2)
    p.y+=48
    p.y=p.center(c.event.upper(), F("black",42))+4
    p.y=p.center("COFFEE · ROASTERY", F("monob",16), spacing=3)+6
    p.y=p.center("Jl. Kenangan No. 1", F("mono",16))+16
    p.y=p.dashed(h=2,x0=m,x1=W-m)+14
    f=F("mono",20)
    p.text(m,p.y,f"ORDER {c.no}",f); p.right(c.now.strftime("%d/%m %H:%M"),f,p.y,x1=W-m); p.y+=34
    p.y=p.dashed(h=2,x0=m,x1=W-m)+14
    for a,b in [("1x CAPPUCCINO","happy"),("1x ICED LATTE","smile"),("1x CROISSANT","laugh")][:max(2,c.n)]:
        p.text(m,p.y,a,f); p.right(b,f,p.y,x1=W-m); p.y+=32
    p.y+=4; p.y=p.rule(2,x0=m,x1=W-m)+10
    fb=F("monob",24); p.text(m,p.y,"TOTAL",fb); p.right("PRICELESS",fb,p.y,x1=W-m); p.y+=44
    p.y=p.dashed(h=2,x0=m,x1=W-m)+16
    rects,p.y=slots(c.layout,m,p.y,W-2*m,gap=10)
    put_photos(p,c,rects)
    p.y+=20
    p.y=p.center("thank you, see you again", F("hand",38))+14
    p.qr_row(c, size=130, x=(W-130)//2) if c.qr is not None else None
    p.y+=4
    p.y=p.center(c.footer, F("monob",18), spacing=3)+10
    return p.finish()


TEMPLATES = [
    ("musik", "Music Receipt", t_musik),
    ("teater", "Theater Ticket", t_teater),
    ("nowplaying", "Now Playing", t_nowplaying),
    ("konser", "Concert Ticket", t_konser),
    ("chat", "Chat", t_chat),
    ("idcard", "ID Card", t_idcard),
    ("poster", "Movie Poster", t_poster),
    ("kopi", "Coffee Receipt", t_kopi),
    ("klasik", "Classic", t_klasik),
    ("sosmed", "Social Profile", t_sosmed),
    ("threads", "Text Feed", t_threads),
    ("xprofil", "Micro Profile", t_xprofil),
    ("facebook", "Social Page", t_facebook),
    ("youtube", "Video Channel", t_youtube),
    ("kalender", "Calendar", t_kalender),
    ("ramalan", "Fortune", t_ramalan),
    ("boarding", "Boarding Pass", t_boarding),
    ("sertifikat", "Certificate", t_sertifikat),
    ("resep", "Prescription", t_resep),
    ("cocok", "Match Test", t_cocok),
    ("kartupos", "Postcard", t_kartupos),
    ("komik", "Comic", t_komik),
    ("strip_rounded", "Strip Rounded", t_strip_rounded),
    ("strip_kotak", "Strip Square", t_strip_kotak),
    ("strip_kapsul", "Strip Capsule", t_strip_kapsul),
    ("strip_perangko", "Strip Stamp", t_strip_perangko),
    ("strip_vintage", "Strip Vintage", t_strip_vintage),
    ("polaroid", "Polaroid", t_polaroid),
    ("film", "Film Strip", t_film),
    ("tiket", "Admission Ticket", t_tiket),
    ("pass", "Guest Pass", t_pass),
    ("koran", "Newspaper", t_koran),
    ("majalah", "Magazine Cover", t_majalah),
    ("belanja", "Shopping Receipt", t_belanja),
    ("elegan", "Elegant", t_elegan),
]
BY_ID = {t[0]: t for t in TEMPLATES}


# ================================================================ TEMPLATE CUSTOM (Studio)

FONT_CHOICES = {
    "geo": "Josefin Sans", "geob": "Josefin Sans Bold", "bebas": "Bebas Neue", "black": "Archivo Black",
    "serif": "Playfair", "serifb": "Playfair Bold", "serifk": "Playfair Black", "hand": "Caveat (tulisan tangan)",
    "mono": "Space Mono", "monob": "Space Mono Bold", "sans": "Inter", "sansb": "Inter Bold",
}
SHAPES = {
    "rect": lambda s: shape_rect,
    "rounded": lambda s: shape_rounded(int(s.get("radius", 18))),
    "stamp": lambda s: shape_stamp,
    "arch": lambda s: shape_arch,
    "cartouche": lambda s: shape_cartouche,
    "cushion": lambda s: shape_cushion,
}
RATIOS = {"auto": None, "wide": 0.56, "landscape": 0.66, "classic": 0.75, "square": 1.0, "portrait": 1.25}


def fill_tokens(text, c):
    t = (text or "")
    for k, v in {"{event}": c.event, "{footer}": c.footer, "{date}": c.date_num, "{date_long}": c.date_long, "{time}": c.time,
                 "{caption}": c.caption, "{no}": c.no, "{day}": c.day.title()}.items():
        t = t.replace(k, v)
    return t.strip()


def _ink_from_logo(src, height, max_w, mode="dark"):
    """Logo -> mask 'tinta' (255 = dicetak). mode dark: bagian gelap jadi tinta; light: bagian terang."""
    im = src.convert("RGBA")
    k = height / im.height
    w = int(im.width * k)
    if w > max_w:
        k = max_w / im.width
        w = max_w
    im = im.resize((max(1, w), max(1, int(im.height * k))), Image.LANCZOS)
    a = im.split()[3]
    g = im.convert("L")
    if mode == "light":
        g = g.point(lambda v: 255 - v)
    ink = Image.composite(g.point(lambda v: 255 - v), Image.new("L", im.size, 0), a)
    return ink.convert("1").convert("L")  # dither halus untuk logo bergradasi


def t_builder(c, s):
    """Template dari form Studio. s = dict spesifikasi."""
    W = c.W
    black = s.get("background") == "black"
    bg, fg = (K, P) if black else (P, K)
    p = Paper(W)
    p.d.rectangle((0, 0, W, p.img.height), fill=bg)
    side = int(s.get("side", 28))
    gap = int(s.get("gap", 14))
    pw = W - 2 * side
    p.y = int(s.get("pad_top", 30))

    def block(key):
        b = s.get(key) or {}
        text = fill_tokens(b.get("text", ""), c)
        if not text:
            return
        if b.get("upper"):
            text = text.upper()
        f = F(b.get("font", "geo") if b.get("font") in FONT_CHOICES else "geo", int(b.get("size", 24)))
        sp = int(b.get("spacing", 0))
        for raw in text.split("\n"):
            for line in (p.wrap(raw, f, pw) if not sp else [raw]):
                p.y = p.center(line, f, fill=fg, spacing=sp) + int(b.get("line_gap", 8))
        p.y += int(b.get("after", 10))

    def divider(kind):
        if kind == "line":
            p.y = p.rule(2, x0=side, x1=W - side) + 18
        elif kind == "dashed":
            p.y = p.dashed(h=3, x0=side, x1=W - side) + 18
        elif kind == "dots":
            p.y = p.dots(r=2, step=10, x0=side, x1=W - side) + 18
        elif kind == "ornament":
            p.ornament(p.y)
            p.y += 26

    # logo
    if s.get("logo") and c.logo_src is not None:
        ink = _ink_from_logo(c.logo_src, int(s.get("logo_h", 90)), pw, s.get("logo_mode", "dark"))
        p.img.paste(fg, ((W - ink.width) // 2, p.y, (W - ink.width) // 2 + ink.width, p.y + ink.height), ink)
        p.y += ink.height + 18
    block("header1")
    block("header2")
    _div_color(p, fg, lambda: divider(s.get("divider_top", "none")))

    # foto
    ratio = RATIOS.get(s.get("photo_ratio", "auto")) or {1: 1.0, 2: 0.85, 3: 0.66, 4: 0.6}[c.n]
    shp = SHAPES.get(s.get("photo_shape", "rect"), SHAPES["rect"])(s)
    keyline = int(s.get("keyline", 0))
    if c.n == 9:
        cw = (pw - 2 * gap) // 3
        rects = [(side + (i % 3) * (cw + gap), p.y + (i // 3) * (cw + gap), cw, cw) for i in range(9)]
    elif c.n == 4 and s.get("grid") == "2x2":
        cw = (pw - gap) // 2
        ch = int(cw * (RATIOS.get(s.get("photo_ratio")) or 1.0))
        rects = [(side + (i % 2) * (cw + gap), p.y + (i // 2) * (ch + gap), cw, ch) for i in range(4)]
    else:
        ph_ = int(pw * ratio)
        rects = [(side, p.y + i * (ph_ + gap), pw, ph_) for i in range(c.n)]
    for i, (x, y, w, h) in enumerate(rects):
        m = _mask(w, h, shp)
        if keyline:
            big = _mask(w + 2 * keyline, h + 2 * keyline, shp)
            p.img.paste(fg, (x - keyline, y - keyline, x + w + keyline, y + h + keyline), big)
            p.img.paste(bg, (x, y, x + w, y + h), m)
        p.img.paste(c.ph(i, w, h), (x, y), m)
    p.y = max(r[1] + r[3] for r in rects) + int(s.get("after_photos", 30))

    _div_color(p, fg, lambda: divider(s.get("divider_bottom", "none")))
    block("footer1")
    block("footer2")

    if s.get("qr", True) and c.qr is not None:
        q = qr_fit(c.qr, int(s.get("qr_size", 120)))
        box = q.width + 20
        bx = (W - box) // 2
        p.d.rounded_rectangle((bx, p.y + 6, bx + box, p.y + 6 + box), radius=10, fill=P)
        p.paste(q, bx + 10, p.y + 16)
        p.y += box + 16
        qt = fill_tokens(s.get("qr_text", ""), c)
        if qt:
            p.y = p.center(qt, F("sans", 18), fill=fg) + 8
    p.y += int(s.get("pad_bottom", 40))

    border = s.get("border", "none")
    if border != "none":
        y1 = p.y - 6
        if border == "line":
            p.d.rectangle((6, 6, W - 7, y1), outline=fg, width=3)
        elif border == "rounded":
            p.d.rounded_rectangle((6, 6, W - 7, y1), radius=26, outline=fg, width=4)
        elif border == "double":
            p.d.rectangle((6, 6, W - 7, y1), outline=fg, width=4)
            p.d.rectangle((16, 16, W - 17, y1 - 10), outline=fg, width=1)
            for cx, cy in [(16, 16), (W - 17, 16), (16, y1 - 10), (W - 17, y1 - 10)]:
                p.diamond(cx, cy, 8, fill=fg)
                p.diamond(cx, cy, 3, fill=bg)
        p.y += 6
    return p.finish(bottom_pad=0)


def _div_color(p, fg, fn):
    """Gambar pemisah dengan warna fg (putih kalau latar hitam)."""
    if fg == K:
        fn()
        return
    # gambar di layer terpisah lalu tempel sebagai putih
    saved_img, saved_d = p.img, p.d
    layer = Image.new("L", p.img.size, P)
    p.img, p.d = layer, ImageDraw.Draw(layer)
    fn()
    p.img, p.d = saved_img, saved_d
    p.img.paste(P, (0, 0), layer.point(lambda v: 255 if v < 128 else 0))


# ---- overlay: frame PNG dengan lubang transparan

def detect_slots(alpha, min_size=40):
    """Cari area transparan (alpha < 128). Return list bbox (x0,y0,x1,y1) urut atas->bawah, kiri->kanan."""
    sc = 4
    small = alpha.resize((max(1, alpha.width // sc), max(1, alpha.height // sc)), Image.NEAREST)
    w, h = small.size
    px = small.load()
    seen = bytearray(w * h)
    boxes = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0 * w + x0] or px[x0, y0] >= 128:
                continue
            stack = [(x0, y0)]
            seen[y0 * w + x0] = 1
            minx = maxx = x0
            miny = maxy = y0
            while stack:
                x, y = stack.pop()
                minx, maxx, miny, maxy = min(minx, x), max(maxx, x), min(miny, y), max(maxy, y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and px[nx, ny] < 128:
                        seen[ny * w + nx] = 1
                        stack.append((nx, ny))
            bx = (minx * sc, miny * sc, min(alpha.width, (maxx + 1) * sc), min(alpha.height, (maxy + 1) * sc))
            if bx[2] - bx[0] >= min_size and bx[3] - bx[1] >= min_size:
                boxes.append(bx)
    boxes.sort(key=lambda b: (b[1] // 20, b[0]))
    return boxes


def load_frame(path, width):
    return load_frame_img(Image.open(path).convert("RGBA"), width)


def load_frame_img(fr, width):
    if fr.width != width:
        fr = fr.resize((width, int(fr.height * width / fr.width)), Image.LANCZOS)
    return fr


def t_overlay(c, s):
    frames = s.get("frames", {})
    fname = frames.get(c.layout)
    if not fname or not c.asset_dir or not os.path.exists(os.path.join(c.asset_dir, os.path.basename(fname))):
        p = Paper(c.W)
        p.y = 24
        p.center("BINGKAI BELUM DIUPLOAD", F("sansb", 22))
        p.y += 8
        p.para_center(f"Layout '{c.layout}' belum memiliki file bingkai PNG.", F("sans", 16))
        p.y += 16
        sl, bottom_y = slots(c.layout, M, p.y, c.W - 2 * M, gap=14)
        for i, (x, y, w, h) in enumerate(sl):
            p.img.paste(c.ph(i, int(w), int(h)), (int(x), int(y)))
            d = ImageDraw.Draw(p.img)
            d.rectangle((int(x), int(y), int(x + w - 1), int(y + h - 1)), outline=K, width=2)
        p.y = bottom_y + 16
        p.dashed()
        p.y += 12
        p.center("Klik 'Edit' pada template ini untuk upload bingkai PNG", F("sans", 15))
        p.y += 14
        return p.finish(bottom_pad=10)
    fr = load_frame(os.path.join(c.asset_dir, os.path.basename(fname)), c.W)
    alpha = fr.split()[3]
    holes = alpha.point(lambda a: 255 if a < 128 else 0)
    canvas = Image.new("L", fr.size, P)
    for i, (x0, y0, x1, y1) in enumerate(detect_slots(alpha)):
        canvas.paste(c.ph(i, x1 - x0, y1 - y0), (x0, y0), holes.crop((x0, y0, x1, y1)))
    g = Image.new("RGB", fr.size, "white")
    g.paste(fr, mask=alpha)
    g = g.convert("L")
    art = g.convert("1").convert("L") if s.get("dither", True) else g.point(lambda v: P if v > 127 else K)
    canvas.paste(art, (0, 0), alpha.point(lambda a: 255 if a >= 128 else 0))
    # teks tambahan opsional di atas frame (mis. tanggal)
    p = Paper(c.W, h=canvas.height + 400)
    p.img.paste(canvas, (0, 0))
    p.y = canvas.height
    extra = fill_tokens(s.get("extra_text", ""), c)
    if extra:
        p.y += 16
        p.para_center(extra, F(s.get("extra_font", "geo") if s.get("extra_font") in FONT_CHOICES else "geo",
                                int(s.get("extra_size", 26))))
    if s.get("qr") and c.qr is not None:
        p.y += 16
        p.qr_row(c, size=130, x=20)
        p.y += 10
    return p.finish(bottom_pad=10 if (extra or s.get("qr")) else 0)


# layout yang didukung template bawaan (selain ini: solo/duo/strip/grid)
BUILTIN_LAYOUTS = {}
DEFAULT_LAYOUTS = {"solo", "duo", "strip", "grid"}


def supports(spec, layout, template_id=None):
    if spec:
        if spec.get("kind") == "overlay":
            return bool(spec.get("frames", {}).get(layout))
        return True
    if template_id:
        return layout in BUILTIN_LAYOUTS.get(template_id, DEFAULT_LAYOUTS)
    return True


def render(template_id, ctx, custom=None):
    """template_id: id bawaan, atau 'c:<id>' untuk template custom dari event."""
    if (ctx.opts or {}).get("lang"):
        set_lang(ctx.opts["lang"])
    ctx.footer, ctx.event = tr(ctx.footer), tr(ctx.event)   # hanya teks bawaan ("TERIMA KASIH", "NAMA EVENT")
    if template_id and template_id.startswith("c:") and custom:
        spec = custom.get(template_id[2:])
        if spec:
            with no_translate():
                return t_overlay(ctx, spec) if spec.get("kind") == "overlay" else t_builder(ctx, spec)
    if template_id in BY_ID and not supports(None, ctx.layout, template_id):
        p = Paper(ctx.W)
        p.y = 40
        p.para_center(f"Template ini tidak mendukung layout '{ctx.layout}'", F("sansb", 26))
        p.y += 20
        return p.finish()
    fn = BY_ID.get(template_id, TEMPLATES[0])[2]
    return fn(ctx)
