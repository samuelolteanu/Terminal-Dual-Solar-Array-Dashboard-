#!/usr/bin/env python3
# v16 — patch pe v15:
# 1. fetch separat vest/sud pentru bare corecte
# 2. scară Y albastră verticală (0-10 kWh, din 2 în 2) cu linii orizontale grid
# 3. linie peak orar (valoare stânga, ora dreapta) similar cu elevația maximă
# deploy: systemctl restart ha-display
# screenshot: fbgrab screenshot.png (se va salva in /root/)
import os, sys, time, struct, math, traceback, re
from datetime import datetime, timedelta
import requests
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════
HA_URL        = "http://192.168.1.x:8123"
HA_TOKEN      = "REDACTAT"

REFRESH       = 10
FB_DEV        = "/dev/fb0"
LATITUDE_DEG  = 45.43 #Galati, Romania
LONGITUDE_DEG = 28.03
UTC_OFFSET    = 3

EL_SUMMER = 68.0
EL_WINTER = 21.0
OVERLAP_THRESH = 3.5
ARC_FRAC  = 0.46

EAST_LEFT     = True
CHART_MAX_KWH = 8.0
TEMP_FONT_SCALE = 1.10

# ═══════════════════════════════════════════════════════════════════════
#  ENTITĂȚI
# ═══════════════════════════════════════════════════════════════════════
REAL_WEST_ENTITY     = "sensor.solar_energy"
REAL_SOUTH_ENTITY    = "sensor.solar_energy_2"
FORECAST_WEST_TODAY  = "sensor.forecast_west_energy_production_today"
FORECAST_SOUTH_TODAY = "sensor.forecast_south_energy_production_today"

WEST = [
    (FORECAST_WEST_TODAY,                                "Astăzi"),
    ("sensor.forecast_west_energy_production_tomorrow",  "Mâine"),
    ("sensor.forecast_west_energy_production_d2",        "Poimâine"),
    ("sensor.forecast_west_energy_production_d3",        "în 3 zile"),
    ("sensor.forecast_west_energy_production_d4",        "în 4 zile"),
    ("sensor.forecast_west_energy_production_d5",        "în 5 zile"),
    ("sensor.forecast_west_energy_production_d6",        "în 6 zile"),
    ("sensor.forecast_west_energy_production_d7",        "în 7 zile"),
]
SOUTH = [
    (FORECAST_SOUTH_TODAY,                               "Astăzi"),
    ("sensor.forecast_south_energy_production_tomorrow", "Mâine"),
    ("sensor.energy_production_d2",                      "Poimâine"),
    ("sensor.energy_production_d3",                      "în 3 zile"),
    ("sensor.energy_production_d4",                      "în 4 zile"),
    ("sensor.energy_production_d5",                      "în 5 zile"),
    ("sensor.energy_production_d6",                      "în 6 zile"),
    ("sensor.energy_production_d7",                      "în 7 zile"),
]
GLOBAL_ENT = [
    ("sensor.global_adjusted_forecast_today",    "_total_fc_today"),
    ("sensor.global_adjusted_forecast_tomorrow", "Total prognozat mâine"),
]

LUX_ENTITY       = "sensor.direct_sun_lux"
SUN_ENTITY       = "sun.sun"
TEMP_EXT_ENTITY  = "sensor.temperatura_exterior"
TEMP_INT_ENTITY  = "sensor.temperatura_interior"
AUTONOMIE_ENTITY = "binary_sensor.free_electricity_baby"

ALL_FORECAST_ENTITIES = WEST + SOUTH + GLOBAL_ENT

# ═══════════════════════════════════════════════════════════════════════
#  CULORI
# ═══════════════════════════════════════════════════════════════════════
C_BG           = (4,   10,  16)
C_TITLE_VEST   = (190, 120,  18)
C_TITLE_SUD    = (235, 185,  48)
C_AUTONOMIE    = (60,  200,  60)
C_LABEL        = (155, 155, 165)
C_VALUE        = (80,  225,  80)
C_UNIT         = (60,  140,  60)
C_GLOBAL       = (90,  185, 255)
C_GLOBAL_U     = (50,  110, 180)
C_ERROR        = (255,  65,  65)
C_TIME         = (155, 155, 175)
C_DIVIDER      = (38,   38,  50)
C_COLSEP       = (35,   35,  48)
C_VDIVIDER     = (30,   38,  55)
C_LUX          = (255, 228,  80)
C_HORIZON      = (30,  85,  30)
C_ARC_TODAY    = (240, 220,  30)
C_ARC_SUMMER   = (60,  110, 220)
C_ARC_WINTER   = (40,   80, 180)
C_LINE_SUMMER  = (55,  100, 200)
C_LINE_WINTER  = (35,   65, 160)
C_LBL_SUMMER   = (70,  120, 220)
C_LBL_WINTER   = (50,   90, 185)
C_SUN          = (255, 225,  35)
C_SUN_SET      = (220, 110,  30)
C_CARD         = (60,  100,  60)
C_EL_MAX       = (130, 130,  50)
C_EL_LINE      = (70,   70,  28)
C_AZ_LINE      = (65,   65,  25)
C_AZ_LBL       = (110, 110,  50)
C_EL_CUR       = (80,  200, 200)
C_SUN_PANEL    = (5,   10,  24)
C_NOON         = (100, 150,  55)
C_TEMP_HOT     = (255, 140,  30)
C_TEMP_COLD    = (60,  130, 220)
C_YESTERDAY    = (80,  225,  80)

C_BAR_SOUTH_ACT = (235, 185,  48)
C_BAR_WEST_ACT  = (190, 120,  18)
C_CURVE_WEST    = (190, 120,  18)
C_CURVE_SOUTH   = (235, 185,  48)
C_CHART_AXIS    = (40,   60,  40)
C_CHART_LBL     = (80,  110,  80)
C_CHART_MAX_LBL = (80,  200, 200)
C_CHART_SCALE   = (40,   80, 160)   # scară Y albastră
C_CHART_GRID    = (22,   45,  90)   # linii grid orizontale
C_PEAK_LINE     = (70,   70,  28)   # linie peak orar — ca EL_LINE
C_PEAK_LBL      = (130, 130,  50)   # text peak

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]
FONT_PATHS_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

# ═══════════════════════════════════════════════════════════════════════
#  FRAMEBUFFER
# ═══════════════════════════════════════════════════════════════════════
def get_fb_geometry():
    try:
        with open('/sys/class/graphics/fb0/virtual_size') as f:
            w, h = map(int, f.read().strip().split(','))
        with open('/sys/class/graphics/fb0/bits_per_pixel') as f:
            bpp = int(f.read().strip())
        return w, h, bpp
    except Exception as e:
        sys.exit(f"[FATAL] {e}")

def img_to_fb_bytes(img, bpp):
    if bpp == 32:
        r, g, b = img.split()
        a = Image.new('L', img.size, 255)
        return Image.merge('RGBA', (b, g, r, a)).tobytes()
    elif bpp == 24:
        r, g, b = img.split()
        return Image.merge('RGB', (b, g, r)).tobytes()
    elif bpp == 16:
        try:
            import numpy as np
            arr = np.array(img, dtype=np.uint16)
            rgb565 = ((arr[:,:,0]>>3)<<11)|((arr[:,:,1]>>2)<<5)|(arr[:,:,2]>>3)
            return rgb565.astype('<u2').tobytes()
        except ImportError:
            out = bytearray()
            for rv, gv, bv in img.getdata():
                v = ((rv&0xF8)<<8)|((gv&0xFC)<<3)|(bv>>3)
                out += struct.pack('<H', v)
            return bytes(out)
    else:
        raise ValueError(f"bpp {bpp}")

def write_fb(img, bpp):
    with open(FB_DEV, 'wb') as fb:
        fb.write(img_to_fb_bytes(img, bpp))

def disable_blanking():
    for path in ['/sys/class/graphics/fb0/blank', '/sys/class/graphics/fb1/blank']:
        try:
            with open(path, 'w') as f: f.write('0')
        except: pass
    for tty in ['/dev/tty0', '/dev/tty1', '/dev/console']:
        try:
            with open(tty, 'wb') as t: t.write(b'\033[9;0]\033[14;0]')
        except: pass
    try:
        os.system('setterm --blank 0 --powerdown 0 --term linux < /dev/tty1 > /dev/tty1 2>/dev/null')
    except: pass

# ═══════════════════════════════════════════════════════════════════════
#  FONT
# ═══════════════════════════════════════════════════════════════════════
def load_font(size, bold=True):
    paths = FONT_PATHS if bold else (FONT_PATHS_REG + FONT_PATHS)
    for path in paths:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()

def tw(draw, text, font):
    try: return int(draw.textlength(text, font=font))
    except AttributeError:
        try: return int(font.getlength(text))
        except: return len(text) * max(8, getattr(font, 'size', 10))

def th(font):
    try:
        bb = font.getbbox("Ag")
        return bb[3] - bb[1]
    except:
        return getattr(font, 'size', 12)

def build_fonts(height):
    PAD_H  = height * 0.013
    usable = height - PAD_H * 9
    base   = max(10, int(usable / 22.0))
    return {
        'title'   : load_font(int(base * 1.22)),
        'label'   : load_font(int(base * 1.0)),
        'value'   : load_font(int(base * 1.10)),
        'small'   : load_font(int(base * 0.68)),
        'prog'    : load_font(int(base * 0.60), bold=False),
        'sun_icon': load_font(int(base * 2.5)),
        'lux_arc' : load_font(int(base * 0.80)),
        'el_arc'  : load_font(int(base * 0.75)),
        'el_max'  : load_font(int(base * 0.64), bold=False),
        'temp'    : load_font(int(base * 0.64 * TEMP_FONT_SCALE)),
        'chart'   : load_font(int(base * 0.56), bold=False),
        'base'    : base,
    }

# ═══════════════════════════════════════════════════════════════════════
#  HOME ASSISTANT
# ═══════════════════════════════════════════════════════════════════════
_HA_HEADERS = None

def init_ha():
    global _HA_HEADERS
    _HA_HEADERS = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

def _get(entity_id):
    try:
        r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_HA_HEADERS, timeout=6)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def fetch_sensor(entity_id):
    d = _get(entity_id)
    if not d: return 'OFFLINE', ''
    state = d.get('state', 'N/A')
    if state.lower() in ('unknown', 'unavailable', 'none', ''): return state.lower(), ''
    unit = d.get('attributes', {}).get('unit_of_measurement', '') or ''
    try: state = f"{float(state):.2f}"
    except: pass
    return state, unit

def is_unavailable(val):
    return val.lower() in ('unknown','unavailable','none','offline','??','n/a','') \
           or val.startswith('http') or val.startswith('HTTP')

def _history_for_day(entity_id, date):
    start = f"{date}T00:00:00"
    end   = f"{date}T23:59:59"
    url   = (f"{HA_URL}/api/history/period/{start}"
             f"?filter_entity_id={entity_id}&end_time={end}&minimal_response=true")
    try:
        r = requests.get(url, headers=_HA_HEADERS, timeout=10)
        if r.status_code == 200:
            j = r.json()
            if j and len(j) > 0: return j[0]
    except: pass
    return []

def _first_valid_float(entries):
    for e in entries:
        s = e.get('state', '')
        if s not in ('unknown', 'unavailable', 'none', ''):
            try: return float(s)
            except: pass
    return None

def _last_valid_float(entries):
    for e in reversed(entries):
        s = e.get('state', '')
        if s not in ('unknown', 'unavailable', 'none', ''):
            try: return float(s)
            except: pass
    return None

def _noon_valid_float(entries):
    best_val, best_diff = None, 999999
    for e in entries:
        s = e.get('state', '')
        if s in ('unknown', 'unavailable', 'none', ''): continue
        try: val = float(s)
        except: continue
        lc = e.get('last_changed', '') or e.get('last_updated', '')
        if not lc: continue
        try:
            if lc.endswith('Z'): lc = lc[:-1] + '+00:00'
            dt_local = datetime.fromisoformat(lc).astimezone()
            noon     = dt_local.replace(hour=12, minute=0, second=0, microsecond=0)
            diff     = abs((dt_local - noon).total_seconds())
            if diff < best_diff:
                best_diff, best_val = diff, val
        except: pass
    return best_val

def parse_ha_time(dt_str):
    if not dt_str: return None
    try:
        s = dt_str.strip()
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s).astimezone().strftime("%H:%M")
    except:
        m = re.search(r'T(\d{2}):(\d{2})', dt_str)
        return f"{m.group(1)}:{m.group(2)}" if m else None

def fetch_sun():
    d = _get(SUN_ENTITY)
    if not d: return None
    a = d.get('attributes', {})
    el = a.get('elevation')
    if el is None: return None
    return {
        'elevation': float(el),
        'azimuth':   float(a['azimuth']) if a.get('azimuth') is not None else 180.0,
        'noon_str':  parse_ha_time(a.get('next_noon')),
    }

def max_elevation_today():
    try:
        doy  = datetime.now().timetuple().tm_yday
        B    = math.radians((360 / 365) * (doy - 81))
        decl = math.radians(23.45 * math.sin(B))
        return round(90.0 - LATITUDE_DEG + math.degrees(decl), 1)
    except: return None

def calc_sunrise_sunset():
    try:
        doy  = datetime.now().timetuple().tm_yday
        lat  = math.radians(LATITUDE_DEG)
        B    = math.radians((360 / 365) * (doy - 81))
        decl = math.radians(23.45 * math.sin(B))
        cos_ha = max(-1.0, min(1.0, -math.tan(lat) * math.tan(decl)))
        ha_h   = math.degrees(math.acos(cos_ha)) / 15.0
        solar_noon = 12.0 + UTC_OFFSET - LONGITUDE_DEG / 15.0
        return solar_noon - ha_h, solar_noon + ha_h
    except:
        return 6.5, 20.0

def fetch_lux():
    val, _ = fetch_sensor(LUX_ENTITY)
    if is_unavailable(val): return None
    try: return f"{float(val):.0f} lux"
    except: return None

def fetch_temp():
    ext_v, _ = fetch_sensor(TEMP_EXT_ENTITY)
    int_v, _ = fetch_sensor(TEMP_INT_ENTITY)
    if is_unavailable(ext_v): return None, None
    try:
        ext_f = float(ext_v)
        try:    color = C_TEMP_HOT if ext_f > float(int_v) else C_TEMP_COLD
        except: color = C_LABEL
        return f"{ext_f:.1f}°C", color
    except: return None, None

def fetch_autonomie():
    d = _get(AUTONOMIE_ENTITY)
    if not d: return False
    return d.get('state', '').lower() == 'on'

def fetch_today_generation(entity_id):
    try:
        r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_HA_HEADERS, timeout=6)
        if r.status_code != 200: return None
        d = r.json()
        state = d.get('state', '')
        if state.lower() in ('unknown', 'unavailable', 'none', ''): return None
        current = float(state)
        today   = datetime.now().date()
        entries = _history_for_day(entity_id, today)
        first   = _first_valid_float(entries)
        if first is None: return 0.0
        return max(0.0, current - first)
    except: return None

def fetch_yesterday_generation(entity_id):
    try:
        yesterday = datetime.now().date() - timedelta(days=1)
        entries   = _history_for_day(entity_id, yesterday)
        first     = _first_valid_float(entries)
        last      = _last_valid_float(entries)
        if first is None or last is None: return None
        return max(0.0, last - first)
    except: return None

def fetch_yesterday_forecast(entity_id):
    try:
        yesterday = datetime.now().date() - timedelta(days=1)
        entries   = _history_for_day(entity_id, yesterday)
        if not entries: return None
        val = _noon_valid_float(entries)
        if val is not None: return val
        return _last_valid_float(entries)
    except: return None

def fetch_wh_period(entity_id):
    d = _get(entity_id)
    if not d: return {}
    wh = d.get('attributes', {}).get('wh_period', {})
    if not wh: return {}
    result = {}
    for ts_str, val in wh.items():
        try:
            s = str(ts_str).strip()
            if s.endswith('Z'): s = s[:-1] + '+00:00'
            dt = datetime.fromisoformat(s).astimezone()
            result[dt.hour] = float(val)
        except: pass
    return result

def fetch_hourly_actuals_single(entity_id):
    """
    Delta kWh per oră pentru o singură entitate energy (kWh cumulative).
    Returnează {hour_int: kwh_delta}.
    """
    today  = datetime.now().date()
    now_dt = datetime.now().astimezone()
    result = {}

    entries = _history_for_day(entity_id, today)
    if not entries: return result

    tv = []
    for e in entries:
        lc = e.get('last_changed') or e.get('last_updated', '')
        s  = e.get('state', '')
        if s in ('unknown', 'unavailable', 'none', ''): continue
        try:
            if lc.endswith('Z'): lc = lc[:-1] + '+00:00'
            tv.append((datetime.fromisoformat(lc).astimezone(), float(s)))
        except: pass
    if not tv: return result
    tv.sort(key=lambda x: x[0])

    def val_at(target):
        best = None
        for dt, v in tv:
            if dt <= target: best = v
            else: break
        return best

    for h in range(now_dt.hour + 1):
        h_start = now_dt.replace(hour=h, minute=0, second=0, microsecond=0)
        h_end   = now_dt.replace(hour=h+1, minute=0, second=0, microsecond=0) \
                  if h < now_dt.hour else now_dt
        v0 = val_at(h_start)
        v1 = val_at(h_end)
        if v0 is not None and v1 is not None:
            result[h] = max(0.0, v1 - v0)

    return result

def fetch_all():
    data = {}
    for eid, _ in ALL_FORECAST_ENTITIES:
        data[eid] = fetch_sensor(eid)
    data['_sun']       = fetch_sun()
    data['_lux']       = fetch_lux()
    data['_temp']      = fetch_temp()
    data['_autonomie'] = fetch_autonomie()
    data['_gen_vest']  = fetch_today_generation(REAL_WEST_ENTITY)
    data['_gen_sud']   = fetch_today_generation(REAL_SOUTH_ENTITY)
    data['_wh_south']  = fetch_wh_period(FORECAST_SOUTH_TODAY)
    data['_wh_west']   = fetch_wh_period(FORECAST_WEST_TODAY)
    return data

def fmt1(v):
    if v is None: return '??'
    try: return f"{float(v):.1f}"
    except: return '??'

# ═══════════════════════════════════════════════════════════════════════
#  SPLINE CATMULL-ROM + CURBE
# ═══════════════════════════════════════════════════════════════════════
def catmull_rom(pts, steps=10):
    if len(pts) < 2: return list(pts)
    n = len(pts)
    out = []
    for i in range(n - 1):
        p0 = pts[max(0, i-1)]
        p1 = pts[i]
        p2 = pts[i+1]
        p3 = pts[min(n-1, i+2)]
        for s in range(steps):
            t  = s / steps
            t2, t3 = t*t, t*t*t
            x = 0.5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            out.append((int(x), int(y)))
    out.append(pts[-1])
    return out

def draw_dashed_curve(draw, pts, color, dash=6, gap=4, width=1):
    if len(pts) < 2: return
    acc = 0; drawing = True
    for i in range(len(pts)-1):
        seg = math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
        if seg < 0.5: continue
        if drawing:
            limit = dash - acc
            if seg <= limit:
                draw.line([pts[i], pts[i+1]], fill=color, width=width)
                acc += seg
                if acc >= dash: acc = 0; drawing = False
            else:
                fx = pts[i][0]+(pts[i+1][0]-pts[i][0])*limit/seg
                fy = pts[i][1]+(pts[i+1][1]-pts[i][1])*limit/seg
                draw.line([pts[i], (int(fx),int(fy))], fill=color, width=width)
                acc = 0; drawing = False
        else:
            acc += seg
            if acc >= gap: acc = 0; drawing = True

def draw_dotdash_curve(draw, pts, color, dot=2, dash=8, gap=6, width=1):
    if len(pts) < 2: return
    pattern = [dot, gap, dash, gap]
    acc = 0; cur_phase = 0
    for i in range(len(pts)-1):
        seg = math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
        if seg < 0.5: continue
        remaining = seg
        px,py = pts[i]; nx,ny = pts[i+1]
        while remaining > 0:
            phase_len = pattern[cur_phase % 4]
            step = min(remaining, phase_len - acc)
            draw_this = (cur_phase % 2 == 0)
            if draw_this:
                ox = int(px+(nx-px)*(seg-remaining)/seg)
                oy = int(py+(ny-py)*(seg-remaining)/seg)
                tx = int(px+(nx-px)*(seg-remaining+step)/seg)
                ty = int(py+(ny-py)*(seg-remaining+step)/seg)
                draw.line([(ox,oy),(tx,ty)], fill=color, width=width)
            acc += step; remaining -= step
            if acc >= phase_len: acc = 0; cur_phase += 1

# ═══════════════════════════════════════════════════════════════════════
#  GRAFIC SOARE
# ═══════════════════════════════════════════════════════════════════════
def az_to_x(az, arc_cx, arc_rx):
    return int(arc_cx - (az - 180) / 90.0 * arc_rx)

def arc_points_fn(max_el, arc_cx, arc_cy, arc_rx, arc_ry, n=120):
    pts = []
    for i in range(n + 1):
        t    = i / n
        az_t = 90 + t * 180
        el_t = max_el * math.sin(t * math.pi)
        pts.append((az_to_x(az_t, arc_cx, arc_rx),
                    int(arc_cy - (el_t / 90.0) * arc_ry)))
    return pts

def draw_arc_line(draw, pts, color, width=2):
    for i in range(len(pts)-1):
        draw.line([pts[i], pts[i+1]], fill=color, width=width)

def dashed_hline(draw, x0, x1, y, color, on=5, off=5):
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x+on, x1), y)], fill=color, width=1)
        x += on + off

def draw_elevation_line(draw, el, label_left, label_right,
                        arc_cx, arc_cy, arc_rx, arc_ry,
                        x0, x1, c_line, c_lbl, f_em, PAD, label_y_off=0):
    y = int(arc_cy - (el / 90.0) * arc_ry)
    dashed_hline(draw, x0 + PAD, x1 - PAD, y, c_line)
    ty = y - th(f_em) - 2 + label_y_off
    draw.text((x0 + PAD + 2, ty), label_left,  font=f_em, fill=c_lbl)
    draw.text((x1 - PAD - 2, ty), label_right, font=f_em, fill=c_lbl, anchor='rt')

def draw_arc_arrow(draw, sun_px, sun_py, t_sun, arc_rx, arc_ry, max_el, color, R):
    """Săgeată care indică mișcarea spre VEST, adaptându-se la variabila EAST_LEFT."""
    
    # Factor de direcție: 
    # Dacă EAST_LEFT = True (E în stânga, V în dreapta), mișcarea e spre dreapta (+1)
    # Dacă EAST_LEFT = False (E în dreapta, V în stânga), mișcarea e spre stânga (-1)
    side = 1.0 if EAST_LEFT else -1.0

    # 1. Calculăm vectorul tangent real (nx, ny) adaptat orientării
    dpx = 2.0 * arc_rx * side
    dpy = -(max_el * math.pi * math.cos(t_sun * math.pi) / 90.0) * arc_ry
    mag = math.sqrt(dpx*dpx + dpy*dpy)
    if mag < 1e-6: return
    nx, ny = dpx/mag, dpy/mag

    # 2. Vectorul orizontal "trișat" (tot timpul spre VEST conform modului ales)
    hx, hy = 1.0 * side, 0.0

    # 3. Mediază cele două direcții (Bisectoarea) pentru a nu se suprapune cu arcul
    fx = nx + hx
    fy = ny + hy
    f_mag = math.sqrt(fx*fx + fy*fy)
    if f_mag < 1e-6:
        fx, fy = hx, hy
    else:
        fx, fy = fx/f_mag, fy/f_mag

    # 4. Desenare (Originea în centrul soarelui)
    sx, sy = sun_px, sun_py
    ALEN = R * 2  #lungime
    
    ex = int(sx + fx * ALEN)
    ey = int(sy + fy * ALEN)
    
    # Corpul săgeții
    draw.line([(sx, sy), (ex, ey)], fill=color, width=2)
    
    # Vârful ascuțit
    angle = math.atan2(fy, fx)
    head_size = ALEN * 0.25
    for s_angle in (+0.4, -0.4):
        draw.line([(ex, ey), (int(ex - head_size*math.cos(angle+s_angle)),
                               int(ey - head_size*math.sin(angle+s_angle)))],
                  fill=color, width=2)

def draw_sun_arc(draw, x0, y0, w, h, sun_data, max_el, fonts, lux_str):
    f_la=fonts['lux_arc']; f_ea=fonts['el_arc']; f_em=fonts['el_max']
    f_prog=fonts['prog']; base=fonts['base']
    PAD = max(5, int(min(w,h)*0.03))

    if not sun_data:
        draw.text((x0+w//2,y0+h//2),"sun.sun nedisponibil",font=fonts['small'],fill=C_ERROR,anchor='mm')
        return

    el=sun_data['elevation']; az=sun_data['azimuth']
    noon=sun_data.get('noon_str'); max_el=max_el or 55.0; above=el>-1.0
    card_h=th(f_prog)+PAD*2
    arc_rx=(w-PAD*4)//2
    arc_ry=min(h-card_h-PAD*2, int(arc_rx*1.15))
    arc_cx=x0+w//2
    zone_mid=(y0+(y0+h-card_h))//2
    arc_cy=zone_mid+int((EL_SUMMER/90.0)*arc_ry/2)
    arc_cy=min(arc_cy,y0+h-card_h-PAD)
    arc_cy=max(arc_cy,y0+int((EL_SUMMER/90.0)*arc_ry)+PAD)

    draw_arc_line(draw,arc_points_fn(EL_SUMMER,arc_cx,arc_cy,arc_rx,arc_ry),C_ARC_SUMMER,width=2)
    draw_arc_line(draw,arc_points_fn(EL_WINTER,arc_cx,arc_cy,arc_rx,arc_ry),C_ARC_WINTER,width=2)
    draw_arc_line(draw,arc_points_fn(max_el,arc_cx,arc_cy,arc_rx,arc_ry,n=240),C_ARC_TODAY,width=2)

    near_summer=abs(max_el-EL_SUMMER)<OVERLAP_THRESH
    near_winter=abs(max_el-EL_WINTER)<OVERLAP_THRESH
    draw_elevation_line(draw,max_el,noon or "",f"{max_el:.1f}°",arc_cx,arc_cy,arc_rx,arc_ry,x0,x0+w,C_EL_LINE,C_EL_MAX,f_em,PAD)
    if not near_summer:
        draw_elevation_line(draw,EL_SUMMER,"21.iun",f"{EL_SUMMER:.0f}°",arc_cx,arc_cy,arc_rx,arc_ry,x0,x0+w,C_LINE_SUMMER,C_LBL_SUMMER,f_em,PAD)
    else:
        draw_elevation_line(draw,max_el,"21.iun",f"{EL_SUMMER:.0f}°",arc_cx,arc_cy,arc_rx,arc_ry,x0,x0+w,C_LINE_SUMMER,C_LBL_SUMMER,f_em,PAD,label_y_off=th(f_em)+3)
    if not near_winter:
        draw_elevation_line(draw,EL_WINTER,"21.dec",f"{EL_WINTER:.0f}°",arc_cx,arc_cy,arc_rx,arc_ry,x0,x0+w,C_LINE_WINTER,C_LBL_WINTER,f_em,PAD)
    else:
        draw_elevation_line(draw,max_el,"21.dec",f"{EL_WINTER:.0f}°",arc_cx,arc_cy,arc_rx,arc_ry,x0,x0+w,C_LINE_WINTER,C_LBL_WINTER,f_em,PAD,label_y_off=th(f_em)+3)

    draw.line([(x0+PAD,arc_cy),(x0+w-PAD,arc_cy)],fill=C_HORIZON,width=2)
    lbl_left="E" if EAST_LEFT else "V"; lbl_right="V" if EAST_LEFT else "E"
    draw.text((x0+PAD+3,arc_cy+3),lbl_left,font=f_prog,fill=C_CARD)
    draw.text((arc_cx,arc_cy+3),"S",font=f_prog,fill=C_CARD,anchor='mt')
    draw.text((x0+w-PAD-3,arc_cy+3),lbl_right,font=f_prog,fill=C_CARD,anchor='rt')

    el_cl=max(0.0,min(max_el,el)) if above else 0.0
    sin_t=(el_cl/max_el) if max_el>0 else 0
    t_val=math.asin(max(0.0,min(1.0,sin_t)))/math.pi
    t_sun=t_val if az<180 else 1.0-t_val
    sun_px=int(arc_cx-arc_rx+2*arc_rx*t_sun) if EAST_LEFT else int(arc_cx+arc_rx-2*arc_rx*t_sun)
    sun_py=int(arc_cy-(el/90.0)*arc_ry) if above else arc_cy
    sun_color=C_SUN if (above and el>8) else (C_SUN_SET if above else (65,65,65))
    R=max(10,int(base*0.52))
    for r_,frac in [(R+20,0.05),(R+13,0.13),(R+7,0.28),(R+3,0.60),(R,1.0)]:
        c=tuple(min(255,int(cv*frac+C_SUN_PANEL[i]*(1-frac))) for i,cv in enumerate(sun_color))
        draw.ellipse([sun_px-r_,sun_py-r_,sun_px+r_,sun_py+r_],fill=c)
    draw.ellipse([sun_px-R,sun_py-R,sun_px+R,sun_py+R],fill=sun_color)
    if above and sun_py<arc_cy-R:
        for yi in range(sun_py+R+4,arc_cy,9):
            draw.line([(sun_px,yi),(sun_px,min(yi+5,arc_cy))],fill=C_AZ_LINE,width=1)
    draw.text((sun_px,arc_cy+th(f_prog)+3),f"{az:.0f}°",font=f_em,fill=C_AZ_LBL,anchor='mt')
    off=R+8
    if lux_str and above:
        is_left=(sun_px<arc_cx)
        lux_x=sun_px+off if is_left else sun_px-off
        draw.text((lux_x,sun_py),lux_str,font=f_la,fill=C_LUX,anchor='lm' if is_left else 'rm')
    if above:
        draw.text((sun_px,sun_py-R-5),f"{el:.1f}°",font=f_ea,fill=C_EL_CUR,anchor='mb')
    if above:
        # Culoarea săgeții: aceeași cu a soarelui, dar puțin mai discretă (stinsă)
        arrow_color = tuple(max(0, c - 40) for c in sun_color)
        
        # Apelăm noua logică pentru săgeata lungă
        draw_arc_arrow(draw, sun_px, sun_py, t_sun, arc_rx, arc_ry, max_el, arrow_color, R)

# ═══════════════════════════════════════════════════════════════════════
#  GRAFIC PRODUCȚIE
# ═══════════════════════════════════════════════════════════════════════
def draw_production_chart(draw, x0, y0, w, h,
                          wh_south, wh_west,
                          actual_west, actual_south,
                          fonts):
    """
    actual_west, actual_south: {hour: kWh} separat pentru fiecare sursă.
    """
    f_ch = fonts['chart']
    PAD  = max(4, int(min(w, h) * 0.025))

    sunrise, sunset = calc_sunrise_sunset()
    h_start = max(0,  int(sunrise))
    h_end   = min(23, int(sunset) + 1)
    num_h   = max(h_end - h_start, 1)

    label_h  = th(f_ch) + 6
    legend_h = th(f_ch) + 4
    SCALE_W  = tw(draw, "10", f_ch) + 6   # lățime coloană scară Y stânga

    # Coordonate zone grafic
    cx0 = x0 + PAD + SCALE_W
    cx1 = x0 + w - PAD
    cy0 = y0 + PAD + legend_h
    cy1 = y0 + h - label_h - PAD
    cw  = cx1 - cx0
    ch  = cy1 - cy0
    if cw < 10 or ch < 10: return

    bar_w = cw / num_h
    Y_MAX = CHART_MAX_KWH

    def kwh_to_y(kwh):
        return cy1 - int(min(kwh, Y_MAX) / Y_MAX * ch)

    def hour_to_x_center(hh):
        i = hh - h_start
        return (cx0 + (i+0.5)*bar_w) if EAST_LEFT else (cx1 - (i+0.5)*bar_w)

    def hour_to_x_left(hh):
        i = hh - h_start
        return int(cx0 + i*bar_w)+1 if EAST_LEFT else int(cx1-(i+1)*bar_w)+1

    def hour_to_x_right(hh):
        i = hh - h_start
        return int(cx0+(i+1)*bar_w)-1 if EAST_LEFT else int(cx1-i*bar_w)-1

    # ── Scară Y (albastră, stânga, din 2 în 2 kWh) ───────────────────
    for step_kwh in range(0, int(Y_MAX)+1, 2):
        gy = kwh_to_y(step_kwh)
        # Linie grid orizontală (toată lățimea graficului)
        draw.line([(cx0, gy), (cx1, gy)], fill=C_CHART_GRID, width=1)
        # Etichetă scară stânga
        lbl = str(step_kwh)
        lx  = x0 + PAD + SCALE_W - tw(draw, lbl, f_ch) - 2
        draw.text((lx, gy - th(f_ch)//2), lbl, font=f_ch, fill=C_CHART_SCALE)

    # Linie bază
    draw.line([(cx0, cy1), (cx1, cy1)], fill=C_CHART_AXIS, width=1)

    # ── Bare actual: Vest jos, Sud sus ────────────────────────────────
    # Peak orar tracking
    peak_kwh  = 0.0
    peak_hour = None

    for hh in range(h_start, h_end):
        act_w = actual_west.get(hh)
        act_s = actual_south.get(hh)
        if act_w is None and act_s is None: continue

        act_w = act_w or 0.0
        act_s = act_s or 0.0
        total = act_w + act_s

        bx0 = hour_to_x_left(hh)
        bx1 = hour_to_x_right(hh)
        if bx1 <= bx0: bx1 = bx0 + 1

        yw = kwh_to_y(act_w)
        ys = kwh_to_y(act_w + act_s)

        if yw < cy1:
            draw.rectangle([(bx0, yw), (bx1, cy1)], fill=C_BAR_WEST_ACT)
        if ys < yw:
            draw.rectangle([(bx0, ys), (bx1, yw)], fill=C_BAR_SOUTH_ACT)

        if total > peak_kwh:
            peak_kwh  = total
            peak_hour = hh

    # ── Curbe smooth prognoze ─────────────────────────────────────────
    pts_west  = []
    pts_total = []
    for hh in range(h_start, h_end):
        fc_w = wh_west.get(hh, 0.0)  / 1000.0
        fc_s = wh_south.get(hh, 0.0) / 1000.0
        xc   = int(hour_to_x_center(hh))
        pts_west.append((xc, kwh_to_y(fc_w)))
        pts_total.append((xc, kwh_to_y(fc_w + fc_s)))

    if pts_west:
        x_orig = cx0 if EAST_LEFT else cx1
        x_end  = cx1 if EAST_LEFT else cx0
        pw_f   = [(x_orig, cy1)] + pts_west  + [(x_end, cy1)]
        pt_f   = [(x_orig, cy1)] + pts_total + [(x_end, cy1)]
        if len(pt_f) >= 3:
            draw_dashed_curve(draw, catmull_rom(pw_f, 8), C_CURVE_WEST,  dash=7, gap=4,  width=2)
            draw_dotdash_curve(draw,catmull_rom(pt_f, 8), C_CURVE_SOUTH, dot=2,  dash=8, gap=6, width=2)

    # ── Linie peak orar ───────────────────────────────────────────────
    if peak_hour is not None and peak_kwh > 0.05:
        peak_y = kwh_to_y(peak_kwh)
        # Linie punctată orizontală (ca elevația maximă)
        dashed_hline(draw, cx0, cx1, peak_y, C_PEAK_LINE, on=5, off=5)
        # Stânga: valoare kWh
        lbl_val = f"{peak_kwh:.2f} kWh"
        draw.text((cx0 + 2, peak_y - th(f_ch) - 2), lbl_val, font=f_ch, fill=C_PEAK_LBL)
        # Dreapta: ora peak
        lbl_ora = f"{peak_hour:02d}:00"
        draw.text((cx1 - 2, peak_y - th(f_ch) - 2), lbl_ora, font=f_ch, fill=C_PEAK_LBL, anchor='rt')

    # ── Etichete ore ──────────────────────────────────────────────────
    for hh in range(h_start, h_end):
        if hh % 2 == 0 or hh == h_start:
            xc = int(hour_to_x_center(hh))
            draw.text((xc, cy1+3), f"{hh:02d}", font=f_ch, fill=C_CHART_LBL, anchor='mt')

    # ── Legendă sus ───────────────────────────────────────────────────
    lx = cx0; ly = y0 + PAD
    rx = cx1
    lbl_sud = "\u00b7-\u00b7-\u00b7 Sud"
    draw.text((rx, ly), lbl_sud, font=f_ch, fill=C_CURVE_SOUTH, anchor='rt')
    rx -= tw(draw, lbl_sud, f_ch) + 12
    lbl_vest = "- - - Vest"
    draw.text((rx, ly), lbl_vest, font=f_ch, fill=C_CURVE_WEST, anchor='rt')

# ═══════════════════════════════════════════════════════════════════════
#  PANEL DREPT
# ═══════════════════════════════════════════════════════════════════════
def draw_right_panel(draw, x0, y0, w, h, sun_data, max_el, fonts,
                     lux_str, wh_south, wh_west, actual_west, actual_south):
    draw.rectangle([(x0,y0),(x0+w,y0+h)], fill=C_SUN_PANEL)
    arc_h   = int(h * ARC_FRAC)
    chart_h = h - arc_h
    sep_y   = y0 + arc_h
    draw.line([(x0,sep_y),(x0+w,sep_y)], fill=(28,38,55), width=1)
    draw_sun_arc(draw, x0, y0, w, arc_h, sun_data, max_el, fonts, lux_str)
    draw_production_chart(draw, x0, sep_y, w, chart_h,
                          wh_south, wh_west, actual_west, actual_south, fonts)

# ═══════════════════════════════════════════════════════════════════════
#  RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def render_frame(W, H, bpp, fonts, data, max_el, error_msg):
    img  = Image.new('RGB', (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    f_title=fonts['title']; f_label=fonts['label']; f_value=fonts['value']
    f_small=fonts['small']; f_prog=fonts['prog']; f_icon=fonts['sun_icon']
    base=fonts['base']
    PAD = max(8, int(H*0.013))
    LEFT_W = int(W*0.585); RIGHT_X = LEFT_W+2
    draw.line([(LEFT_W,0),(LEFT_W,H)], fill=C_VDIVIDER, width=2)

    y = PAD
    ts_str = datetime.now().strftime("%H:%M  %d.%m.%Y")
    if data.get('_autonomie',False):
        draw.text((LEFT_W//2-40,y),"24h \u2190  Autonomie  \u2192 24h",font=f_prog,fill=C_AUTONOMIE,anchor='mt')
    draw.text((LEFT_W-PAD,y),ts_str,font=f_small,fill=C_TIME,anchor='rt')
    y += int(base*0.68*1.65)

    sun_data=data.get('_sun')
    el_now=sun_data['elevation'] if sun_data else 0
    above_now=el_now>-1.0 if sun_data else False
    icon_col=C_SUN if (above_now and el_now>8) else (C_SUN_SET if above_now else (70,70,70))
    icon_h=int(base*2.5*1.1); icon_w=tw(draw,"☀",f_icon)
    icon_x=PAD*2; icon_y=y
    global_row_h=int(base*1.10*1.42)
    global_y=icon_y+max(0,(icon_h-global_row_h*2)//2)

    gen_vest=data.get('_gen_vest'); gen_sud=data.get('_gen_sud')
    fc_val,fc_unit=data.get("sensor.global_adjusted_forecast_today",('??','kWh'))
    if gen_vest is not None or gen_sud is not None:
        gen_total=(gen_vest or 0.0)+(gen_sud or 0.0)
        gen_str=f"{gen_total:.2f}"
    else:
        gen_str='??'
    try:    prog_str=f"{float(fc_val):.1f}"
    except: prog_str=fc_val
    unit_str=f" {fc_unit}".rstrip() if fc_unit else " kWh"

    lbl1="Total Generat Astăzi:"; val1=f"{gen_str}/{prog_str}"; gx=icon_x+icon_w+PAD*2
    draw.text((gx,global_y),lbl1,font=f_label,fill=C_GLOBAL)
    lw1=tw(draw,lbl1,f_label)
    draw.text((gx+lw1+PAD,global_y),val1,font=f_value,fill=C_GLOBAL)
    uw1=tw(draw,val1,f_value)
    draw.text((gx+lw1+PAD+uw1+3,global_y+int(base*0.16)),unit_str,font=f_prog,fill=C_GLOBAL_U)

    eid2,_=GLOBAL_ENT[1]; val2,unit2=data.get(eid2,('??','kWh'))
    try:    val2_fmt=f"{float(val2):.1f}"
    except: val2_fmt=val2
    unit_str2=f" {unit2}".rstrip() if unit2 else " kWh"
    lbl2="Total Prognozat Mâine:"; gy2=global_y+global_row_h
    draw.text((gx,gy2),lbl2,font=f_label,fill=C_GLOBAL)
    lw2=tw(draw,lbl2,f_label)
    draw.text((gx+lw2+PAD,gy2),val2_fmt,font=f_value,fill=C_GLOBAL)
    uw2=tw(draw,val2_fmt,f_value)
    draw.text((gx+lw2+PAD+uw2+3,gy2+int(base*0.16)),unit_str2,font=f_prog,fill=C_GLOBAL_U)
    draw.text((icon_x,icon_y),"☀",font=f_icon,fill=icon_col)
    y=icon_y+icon_h+PAD

    draw.line([(PAD,y),(LEFT_W-PAD,y)],fill=C_DIVIDER,width=2)
    y+=PAD*2; y_col=y
    HALF=LEFT_W//2; row_h=int(base*1.10*1.28); title_h=int(base*1.22*1.45); col_limit=H-PAD

    def draw_column(x_l,x_r,entities,title,c_title,gen_azi,ieri_gen,ieri_prog):
        cx_=(x_l+x_r)//2; y_=y_col
        draw.text((cx_,y_),title,font=f_title,fill=c_title,anchor='mt')
        y_+=title_h
        if y_+row_h<=col_limit:
            ieri_val=f"{fmt1(ieri_gen)}/{fmt1(ieri_prog)}"
            draw.text((x_l+PAD,y_),"Ieri",font=f_label,fill=C_LABEL)
            uw=tw(draw," kWh",f_prog)
            draw.text((x_r-PAD,y_+int(base*0.2))," kWh",font=f_prog,fill=C_UNIT,anchor='rt')
            draw.text((x_r-PAD-uw-4,y_),ieri_val,font=f_value,fill=C_YESTERDAY,anchor='rt')
            y_+=row_h
        for eid,lbl in entities:
            if y_+row_h>col_limit: break
            val,unit=data.get(eid,('??','kWh'))
            unit_str=f" {unit}" if unit else ""
            if lbl=="Astăzi" and gen_azi is not None:
                try:    val=f"{gen_azi:.1f}/{float(val):.1f}"
                except: val=f"{gen_azi:.1f}/{val}"
            draw.text((x_l+PAD,y_),lbl,font=f_label,fill=C_LABEL)
            uw=tw(draw,unit_str,f_prog)
            draw.text((x_r-PAD,y_+int(base*0.2)),unit_str,font=f_prog,fill=C_UNIT,anchor='rt')
            draw.text((x_r-PAD-uw-4,y_),val,font=f_value,fill=C_VALUE,anchor='rt')
            y_+=row_h

    draw_column(0,HALF,WEST,"Instalație Vest",C_TITLE_VEST,data.get('_gen_vest'),data.get('_ieri_gen_vest'),data.get('_ieri_prog_vest'))
    draw_column(HALF,LEFT_W,SOUTH,"Instalație Sud",C_TITLE_SUD,data.get('_gen_sud'),data.get('_ieri_gen_sud'),data.get('_ieri_prog_sud'))
    draw.line([(HALF,y_col),(HALF,H)],fill=C_COLSEP,width=1)

    temp_str,temp_color=data.get('_temp',(None,None))
    if temp_str and temp_color:
        draw.text((PAD*2,H-PAD),f"{temp_str}",font=fonts['temp'],fill=temp_color,anchor='lb')

    draw_right_panel(draw,RIGHT_X,0,W-RIGHT_X,H,
                     data.get('_sun'),max_el,fonts,data.get('_lux'),
                     data.get('_wh_south',{}),data.get('_wh_west',{}),
                     data.get('_actual_west',{}),data.get('_actual_south',{}))

    if error_msg:
        draw.text((LEFT_W//2,H-PAD),error_msg,font=f_prog,fill=C_ERROR,anchor='mb')
    return img

# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    init_ha()
    disable_blanking()
    W,H,bpp=get_fb_geometry()
    print(f"[ha-display v16] {W}×{H} @ {bpp}bpp  refresh={REFRESH}s")
    fonts=build_fonts(H); last_data={}; error_msg=None; loop=0
    history_cache={}; history_cache_time=0; HISTORY_TTL=300
    actual_cache={}; actual_cache_time=0; ACTUAL_TTL=60

    while True:
        loop+=1
        if loop%5==0: disable_blanking()
        now=time.time()

        if now-history_cache_time>HISTORY_TTL:
            history_cache={
                '_ieri_gen_vest' : fetch_yesterday_generation(REAL_WEST_ENTITY),
                '_ieri_gen_sud'  : fetch_yesterday_generation(REAL_SOUTH_ENTITY),
                '_ieri_prog_vest': fetch_yesterday_forecast(FORECAST_WEST_TODAY),
                '_ieri_prog_sud' : fetch_yesterday_forecast(FORECAST_SOUTH_TODAY),
            }
            history_cache_time=now

        if now-actual_cache_time>ACTUAL_TTL:
            actual_cache={
                '_actual_west' : fetch_hourly_actuals_single(REAL_WEST_ENTITY),
                '_actual_south': fetch_hourly_actuals_single(REAL_SOUTH_ENTITY),
            }
            actual_cache_time=now

        new_data=fetch_all()
        new_data.update(history_cache)
        new_data.update(actual_cache)
        max_el=max_elevation_today()

        errors=sum(1 for eid,_ in ALL_FORECAST_ENTITIES if is_unavailable(new_data.get(eid,('??',''))[0]))
        if errors<len(ALL_FORECAST_ENTITIES):
            last_data=new_data
            error_msg=f"⚠  {errors} entități indisponibile" if errors else None
        else:
            error_msg="⚠  HA offline — date vechi"
            keep=('_sun','_lux','_temp','_autonomie','_gen_vest','_gen_sud','_wh_south','_wh_west','_actual_west','_actual_south','_ieri_gen_vest','_ieri_gen_sud','_ieri_prog_vest','_ieri_prog_sud')
            for k in keep:
                if new_data.get(k) is not None: last_data[k]=new_data[k]

        try:
            img=render_frame(W,H,bpp,fonts,last_data,max_el,error_msg)
            write_fb(img,bpp)
        except Exception as e:
            print(f"[ha-display] Render error: {e}",file=sys.stderr)
            traceback.print_exc()
        time.sleep(REFRESH)

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ha-display] Oprit.")
    except Exception:
        traceback.print_exc()
        time.sleep(10)
        sys.exit(1)
