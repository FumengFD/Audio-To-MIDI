#!/usr/bin/env python3
"""
MIDI → MSCZ 全自动整理
  python midi2mscz.py

流程：量化 MIDI → MuseScore CLI 转换 → 修复乐器 → 断行/力度/样式

也可单独处理 MSCZ：
  python midi2mscz.py --mscz some_score.mscz
"""
import mido, subprocess, sys, io, shutil, os, re
import xml.etree.ElementTree as ET
import zipfile, random, string
from pathlib import Path
from collections import defaultdict

# 自动查找 MuseScore
def _find_musescore():
    candidates = [
        Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / r"Programs\MuseScore 4\bin\MuseScore4.exe",
        Path(r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe"),
        "musescore4", "MuseScore4", "musescore3", "MuseScore3",
    ]
    for c in candidates:
        if isinstance(c, str):
            import shutil as sh
            if sh.which(c): return c
        elif isinstance(c, Path) and c.exists():
            return str(c)
    raise FileNotFoundError("MuseScore not found. Install MuseScore 4.")

MUSESCORE_CLI = _find_musescore()
TARGET_TPB = 480
QUANTIZE_GRID = 120        # 16th note
MIN_NOTE_TICKS = 15
VELOCITY_MIN = 10
MEASURES_PER_SYSTEM_MIN = 2
MEASURES_PER_SYSTEM_MAX = 8
SYSTEMS_PER_PAGE = 9
SPATIUM_SCALE = 1.64
STAFF_DISTANCE = 5.0
MIN_STAFF_SPREAD = 3.0
MAX_STAFF_SPREAD = 18.0
TARGET_NOTES_PER_SYSTEM = 40

VELOCITY_DYNAMIC_MAP = [
    (20, "ppp"), (35, "pp"), (48, "p"), (58, "mp"),
    (68, "mf"), (78, "f"), (90, "ff"), (110, "fff"),
]

# ─── GM → MuseScore Instrument Map ──────────────────
GM_TO_MUSE = {
    0: 'piano', 1: 'piano', 2: 'piano', 3: 'piano', 4: 'piano',
    5: 'piano', 6: 'piano', 7: 'piano',
    24: 'guitar-nylon', 25: 'guitar-steel', 26: 'guitar-jazz',
    27: 'guitar-clean', 28: 'guitar-muted', 29: 'guitar-overdrive',
    30: 'guitar-distortion', 31: 'guitar-harmonics',
    32: 'bass-acoustic', 33: 'bass-finger', 34: 'bass-pick',
    35: 'bass-fretless', 36: 'bass-slap', 37: 'bass-slap-2',
    38: 'bass-synth', 39: 'bass-synth-2',
    40: 'violin', 41: 'viola', 42: 'cello', 43: 'contrabass',
    44: 'strings-tremolo', 45: 'strings-pizzicato', 46: 'harp', 47: 'timpani',
    48: 'strings', 49: 'strings-2', 50: 'strings-synth',
    51: 'strings-synth-2', 52: 'choir-aahs', 53: 'voice-oohs',
    54: 'voice-synth', 55: 'orchestra-hit',
    56: 'trumpet', 57: 'trombone', 58: 'tuba', 59: 'trumpet-muted',
    60: 'horn', 61: 'brass', 62: 'brass-synth', 63: 'brass-synth-2',
    64: 'soprano-sax', 65: 'alto-sax', 66: 'tenor-sax', 67: 'baritone-sax',
    68: 'oboe', 69: 'english-horn', 70: 'bassoon', 71: 'clarinet',
    72: 'piccolo', 73: 'flute', 74: 'recorder', 75: 'pan-flute',
    80: 'lead-square', 81: 'lead-sawtooth',
}

INSTRUMENT_NAMES = {
    'drumset':     ('架子鼓, Drums', 'D. Kit', '架子鼓'),
    'piano':       ('钢琴', 'Pno.', '钢琴'),
    'bass-pick':   ('低音吉他, Bass', 'B. Guit.', '低音吉他'),
    'bass-finger': ('低音吉他, Bass', 'B. Guit.', '低音吉他'),
    'bass-guitar': ('低音吉他, Bass', 'B. Guit.', '低音吉他'),
    'guitar-steel':('钢弦吉他, Guitar', 'Guit.', '钢弦吉他'),
    'guitar-nylon':('尼龙弦吉他, Guitar', 'Guit.', '尼龙弦吉他'),
    'guitar-clean':('电吉他, Guitar', 'Guit.', '电吉他'),
    'voice-synth': ('合成人声, Vocals', 'Vo.', '合成人声'),
    'voice':       ('人声, Vocals', 'Vo.', '人声'),
    'strings':     ('弦乐组, Strings', 'Str.', '弦乐组'),
    'strings-2':   ('弦乐组, Strings', 'Str.', '弦乐组'),
    'octave-mandolin': ('八度音曼陀林琴, Guitar', 'OM.', '八度音曼陀林琴'),
}

FALLBACK_MAPPING = {
    '1': 'drumset', '2': 'bass-guitar', '3': 'voice',
    '4': 'octave-mandolin', '5': 'strings', '6': 'strings',
}


# ═════════════════════════════════════════════════════
#  Utility
# ═════════════════════════════════════════════════════
def gen_eid():
    return ''.join(random.choices(string.ascii_letters + string.digits + "+/", k=22))

def vel2dyn(v):
    for t, m in VELOCITY_DYNAMIC_MAP:
        if v <= t: return m
    return "fff"

def note_count(m):
    c = 0
    for v in m.findall('voice'):
        c += len(v.findall('Chord')) + len(v.findall('Note'))
    return c

def build_staff_map(score_el):
    parts = score_el.findall('Part')
    staffs = score_el.findall('Staff')
    m = []; idx = 0
    for p in parts:
        n = len(p.findall('Staff'))
        m.append((p, staffs[idx:idx+n])); idx += n
    return m


# ═════════════════════════════════════════════════════
#  Step 1: Quantize MIDI
# ═════════════════════════════════════════════════════
def resample_midi(mid):
    if mid.ticks_per_beat == TARGET_TPB: return mid
    ratio = TARGET_TPB / mid.ticks_per_beat
    new = mido.MidiFile(ticks_per_beat=TARGET_TPB, type=mid.type)
    for t in mid.tracks:
        nt = mido.MidiTrack()
        for msg in t:
            nm = msg.copy()
            if hasattr(nm, 'time'): nm.time = int(round(msg.time * ratio))
            nt.append(nm)
        new.tracks.append(nt)
    return new

def collect_notes(track):
    notes = []; time = 0; on = {}
    for msg in track:
        time += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            if msg.note in on:
                s, v = on.pop(msg.note); notes.append((s, time - s, msg.note, v))
            on[msg.note] = (time, msg.velocity)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in on:
                s, v = on.pop(msg.note); notes.append((s, time - s, msg.note, v))
    for p, (s, v) in on.items():
        notes.append((s, time - s, p, v))
    return notes

def q_tick(t, g): return int(round(t / g)) * g

def fix_overlaps(notes):
    """保留重叠音符，只把严格重叠的同音高前面音符截短，不删除"""
    by_pitch = defaultdict(list)
    for i, (s, d, p, v) in enumerate(notes):
        by_pitch[p].append((s, d, i, v))
    adj = {}
    for p, grp in by_pitch.items():
        grp.sort(key=lambda x: x[0])
        for j in range(len(grp) - 1):
            sa, da, ia, va = grp[j]
            sb, db, ib, vb = grp[j+1]
            if sb < sa + da:
                # 截短前一个音符，但保留至少 1 个量化单位的时值
                nd = sb - sa
                if nd > QUANTIZE_GRID:
                    adj[ia] = nd
                # 不删除音符
    res = []
    for i, (s, d, p, v) in enumerate(notes):
        if i in adj:
            d = adj[i]
        res.append((s, d, p, v))
    return res

def quantize_midi_file(input_path, output_path):
    print(f"Loading: {Path(input_path).name}")
    mid = mido.MidiFile(input_path)
    print(f"  TPB: {mid.ticks_per_beat}, Tracks: {len(mid.tracks)}")

    mid = resample_midi(mid)
    new_tracks = []
    stats = {'orig': 0, 'out': 0}

    for ti, track in enumerate(mid.tracks):
        if not any(m.type == 'note_on' for m in track):
            new_tracks.append(track); continue
        name = track.name or f'Trk{ti}'
        notes = collect_notes(track)
        stats['orig'] += len(notes)

        # 只量化起始时间，保留原有时值
        for i in range(len(notes)):
            s, d, p, v = notes[i]
            snapped = q_tick(s, QUANTIZE_GRID)
            shift = snapped - s
            notes[i] = (snapped, d + shift, p, v)  # 等量平移，时值不变
        notes.sort(key=lambda x: x[0])
        notes = fix_overlaps(notes)
        stats['out'] += len(notes)

        nt = mido.MidiTrack()
        for msg in track:
            if msg.type not in ('note_on', 'note_off', 'polytouch', 'aftertouch'):
                nt.append(msg.copy())
        events = []
        for s, d, p, v in notes:
            events.append((s, 'on', p, v))
            events.append((max(0, s + d), 'off', p, 0))
        events.sort(key=lambda x: (x[0], 0 if x[1] == 'off' else 1))
        last = 0
        for tick, et, p, v in events:
            delta = max(0, tick - last)
            if et == 'on':
                nt.append(mido.Message('note_on', note=p, velocity=v, time=delta))
            else:
                nt.append(mido.Message('note_off', note=p, velocity=0, time=delta))
            last = tick
        new_tracks.append(nt)
        print(f"  {name}: {len(notes)} notes")

    mid.tracks = new_tracks
    mid.save(output_path)
    print(f"  Orig={stats['orig']} -> {stats['out']}")
    return stats


# ═════════════════════════════════════════════════════
#  Step 2: MuseScore CLI MIDI → MSCZ
# ═════════════════════════════════════════════════════
def midi_to_mscz_via_musescore(midi_path, mscz_out):
    if not Path(MUSESCORE_CLI).exists():
        raise FileNotFoundError(f"MuseScore not found: {MUSESCORE_CLI}")
    cmd = [MUSESCORE_CLI, '-o', str(mscz_out), str(midi_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"MuseScore failed (code {result.returncode}): {result.stderr}")
    return mscz_out


# ═════════════════════════════════════════════════════
#  Step 3: Fix instruments
# ═════════════════════════════════════════════════════
def read_midi_programs(midi_path):
    mid = mido.MidiFile(midi_path)
    progs = {}
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'program_change':
                progs[msg.channel] = msg.program
    return progs

def fix_one_instrument(inst_el, muse_id, hint=None):
    names = INSTRUMENT_NAMES.get(muse_id)
    if names is None:
        names = (hint or muse_id, muse_id[:6], muse_id)
    ln, sn, tn = names
    inst_el.set('id', muse_id)
    for tag, val in [('longName', ln), ('shortName', sn), ('trackName', tn)]:
        el = inst_el.find(tag)
        if el is None: el = ET.SubElement(inst_el, tag)
        el.text = val

def fix_mscz_instruments(mscz_path, midi_ref=None):
    extract = Path(mscz_path).parent / f'_tmp_inst_{os.getpid()}_{id(mscz_path) % 10000}'
    if extract.exists(): shutil.rmtree(extract)
    with zipfile.ZipFile(mscz_path, 'r') as zf:
        zf.extractall(extract)

    try:
        mscx = list(extract.glob('*.mscx'))
        if not mscx:
            return 0
        mscx = mscx[0]
        gm = read_midi_programs(midi_ref) if midi_ref else {}

        tree = ET.parse(str(mscx)); root = tree.getroot(); score = root.find('Score')
        parts = score.findall('Part'); staffs = score.findall('Staff')
        idx = 0; changed = 0

        for part in parts:
            n = len(part.findall('Staff'))
            pid = part.get('id'); inst = part.find('Instrument')
            if inst is None: idx += n; continue

            cur = inst.get('id', '')
            if cur and cur not in ('piano', 'grand-piano', 'keyboard') and cur in INSTRUMENT_NAMES and cur != 'piano':
                print(f"  Part {pid}: {cur} OK")
                idx += n; continue

            correct = FALLBACK_MAPPING.get(pid)
            if correct is None and gm:
                channels = [c for c in sorted(gm) if c != 9]
                pi = int(pid) - 1
                if pi < len(channels):
                    correct = GM_TO_MUSE.get(gm[channels[pi]])
            if correct is None:
                idx += n; continue

            fix_one_instrument(inst, correct)
            names = INSTRUMENT_NAMES.get(correct)
            if names:
                te = part.find('trackName')
                if te is not None: te.text = names[0]
            print(f"  Part {pid}: {cur} -> {correct}")
            changed += 1
            idx += n

        if changed:
            xml_str = ET.tostring(root, encoding='unicode')
            if not xml_str.startswith('<?xml'): xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
            with open(mscx, 'w', encoding='utf-8') as f: f.write(xml_str)
            with zipfile.ZipFile(mscz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for dp, _, fns in os.walk(extract):
                    for fn in fns:
                        fp = os.path.join(dp, fn)
                        zf.write(fp, os.path.relpath(fp, extract))
    finally:
        shutil.rmtree(extract, ignore_errors=True)
    return changed


# ═════════════════════════════════════════════════════
#  Step 4: Clean up score
# ═════════════════════════════════════════════════════
def compute_breaks(part_staff_map):
    best_s, best_n, best_name = None, -1, ""
    for part, staffs in part_staff_map:
        if not staffs: continue
        st = part.find('Staff').find('StaffType')
        if st is None or st.get('group') != 'pitched': continue
        ms = staffs[0].findall('Measure')
        n = sum(note_count(m) for m in ms)
        if n > best_n: best_n, best_s, best_name = n, staffs, part.findtext('trackName', '?')
    if best_s is None:
        for p, s in part_staff_map:
            if s: best_s, best_name = s, p.findtext('trackName', '?'); break
    if best_s is None: return []
    print(f"  Reference: {best_name} ({best_n} notes)")

    ms = best_s[0].findall('Measure')
    dens = [note_count(m) for m in ms]
    breaks = []; pos = 0; num = len(ms)
    while pos < num:
        if num - pos <= MEASURES_PER_SYSTEM_MIN + 1: break
        cum = 0; chosen = pos + MEASURES_PER_SYSTEM_MIN
        max_l = min(pos + MEASURES_PER_SYSTEM_MAX, num - 1)
        for i in range(pos, max_l):
            cum += dens[i]
            if cum >= TARGET_NOTES_PER_SYSTEM and i - pos + 1 >= MEASURES_PER_SYSTEM_MIN:
                chosen = i + 1; break
            if i - pos + 1 >= MEASURES_PER_SYSTEM_MAX:
                chosen = i + 1; break
        else:
            chosen = max_l
        breaks.append(chosen); pos = chosen
    if breaks and breaks[-1] >= num - 1: breaks = breaks[:-1]
    return breaks

def add_breaks(staffs, breaks):
    for st in staffs:
        ms = st.findall('Measure')
        for li, bi in enumerate(breaks):
            if bi >= len(ms): continue
            m = ms[bi]
            if m.find('LayoutBreak') is not None: continue
            lb = ET.SubElement(m, 'LayoutBreak')
            ET.SubElement(lb, 'eid').text = gen_eid()
            sb = ET.SubElement(lb, 'subtype')
            sb.text = 'page' if (li + 1) % SYSTEMS_PER_PAGE == 0 else 'line'

def add_dynamics(staffs):
    t = 0
    for st in staffs:
        prev = None
        for m in st.findall('Measure'):
            vel = None
            for v in m.findall('voice'):
                for ch in v.findall('Chord'):
                    for n in ch.findall('Note'):
                        ve = n.find('velocity')
                        if ve is not None and ve.text: vel = int(ve.text); break
                    if vel: break
                if vel: break
                for n in v.findall('Note'):
                    ve = n.find('velocity')
                    if ve is not None and ve.text: vel = int(ve.text); break
                if vel: break
            if vel is None: continue
            dt = vel2dyn(vel)
            if prev and dt == prev: continue
            if any(v.find('Dynamic') is not None for v in m.findall('voice')):
                prev = dt; continue
            fv = m.find('voice')
            if fv is not None:
                de = ET.Element('Dynamic')
                ET.SubElement(de, 'eid').text = gen_eid()
                ET.SubElement(de, 'subtype').text = dt
                ET.SubElement(de, 'velocity').text = str(vel)
                ET.SubElement(de, 'placement').text = 'below'
                fv.insert(0, de); t += 1
            prev = dt
    return t

def adjust_style(extract_dir):
    mss = Path(extract_dir) / 'score_style.mss'
    if not mss.exists(): return
    with open(mss, 'r', encoding='utf-8') as f: text = f.read()
    for pat, rep in [
        (r'<spatium>[^<]*</spatium>', f'<spatium>{SPATIUM_SCALE}</spatium>'),
        (r'<staffDistance>[^<]*</staffDistance>', f'<staffDistance>{STAFF_DISTANCE}</staffDistance>'),
        (r'<minStaffSpread>[^<]*</minStaffSpread>', f'<minStaffSpread>{MIN_STAFF_SPREAD}</minStaffSpread>'),
        (r'<maxStaffSpread>[^<]*</maxStaffSpread>', f'<maxStaffSpread>{MAX_STAFF_SPREAD}</maxStaffSpread>'),
        (r'<akkoladeDistance>[^<]*</akkoladeDistance>', f'<akkoladeDistance>{STAFF_DISTANCE}</akkoladeDistance>'),
        (r'<minSystemDistance>[^<]*</minSystemDistance>', '<minSystemDistance>7.0</minSystemDistance>'),
        (r'<maxSystemDistance>[^<]*</maxSystemDistance>', '<maxSystemDistance>12.0</maxSystemDistance>'),
        (r'<spreadSystem>[^<]*</spreadSystem>', '<spreadSystem>2.0</spreadSystem>'),
        (r'<spreadSquareBracket>[^<]*</spreadSquareBracket>', '<spreadSquareBracket>1.0</spreadSquareBracket>'),
        (r'<spreadCurlyBracket>[^<]*</spreadCurlyBracket>', '<spreadCurlyBracket>1.0</spreadCurlyBracket>'),
    ]:
        text = re.sub(pat, rep, text)
    with open(mss, 'w', encoding='utf-8') as f: f.write(text)

def cleanup_mscz(mscz_path, output_path):
    extract = Path(mscz_path).parent / f'_tmp_clean_{os.getpid()}_{id(mscz_path) % 10000}'
    if extract.exists(): shutil.rmtree(extract)
    with zipfile.ZipFile(mscz_path, 'r') as zf: zf.extractall(extract)

    try:
        mscx = list(extract.glob('*.mscx'))
        if not mscx:
            return
        mscx = mscx[0]
        print(f"Processing: {mscx.name}")

        with open(mscx, 'r', encoding='utf-8') as f: xml_text = f.read()
        root = ET.fromstring(xml_text); score = root.find('Score')
        smap = build_staff_map(score)

        for part, staffs in smap:
            track = part.findtext('trackName', '?')
            nm = len(staffs[0].findall('Measure')) if staffs else 0
            grp = ''
            staff_el = part.find('Staff')
            if staff_el is not None:
                stt = staff_el.find('StaffType')
                grp = stt.get('group', '') if stt is not None else ''
            print(f"  Part {part.get('id')}: {track} [{grp}] {nm}m")

        print("[1/3] Breaks...")
        breaks = compute_breaks(smap)
        print(f"  {len(breaks)} breaks at: {[b+1 for b in breaks]}")
        for _, staffs in smap: add_breaks(staffs, breaks)

        print("[2/3] Dynamics...")
        td = 0
        for part, staffs in smap:
            staff_el = part.find('Staff')
            st = staff_el.find('StaffType') if staff_el is not None else None
            if st is None or st.get('group') != 'pitched' or not staffs: continue
            n = add_dynamics(staffs); td += n
            print(f"  Part {part.get('id')}: {n}")
        print(f"  Total: {td}")

        print("[3/3] Style...")
        adjust_style(extract)

        xml_str = ET.tostring(root, encoding='unicode')
        if not xml_str.startswith('<?xml'): xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        with open(mscx, 'w', encoding='utf-8') as f: f.write(xml_str)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for dp, _, fns in os.walk(extract):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    zf.write(fp, os.path.relpath(fp, extract))
    finally:
        shutil.rmtree(extract, ignore_errors=True)
    print(f"  Done: {Path(output_path).name}")


# ═════════════════════════════════════════════════════
#  Pipeline
# ═════════════════════════════════════════════════════
def pipeline_midi(midi_path):
    ws = midi_path.parent; stem = midi_path.stem
    q_mid = ws / f"{stem}_q.mid"
    raw = ws / f"{stem}_q.mscz"
    final = ws / f"{stem}_final.mscz"
    for f in [q_mid, raw, final]:
        if f.exists(): f.unlink()

    print(f"\n{'='*55}\nInput: {midi_path.name}\n{'='*55}")

    print("\n── Step 1/4: Quantize MIDI ──")
    quantize_midi_file(str(midi_path), str(q_mid))

    print("\n── Step 2/4: MuseScore MIDI→MSCZ ──")
    midi_to_mscz_via_musescore(str(q_mid), str(raw))

    print("\n── Step 3/4: Fix instruments ──")
    fix_mscz_instruments(str(raw), midi_ref=str(q_mid))

    print("\n── Step 4/4: Layout + dynamics + style ──")
    cleanup_mscz(str(raw), str(final))

    q_mid.unlink(missing_ok=True); raw.unlink(missing_ok=True)
    print(f"\n{'='*55}\nDone: {final.name}\n{'='*55}")
    return final


def pipeline_mscz(mscz_path):
    ws = mscz_path.parent; stem = mscz_path.stem
    mid_ref = None
    for mf in ws.glob('*.mid'):
        mid_ref = str(mf); break

    print(f"\n── Fix instruments ──")
    fix_mscz_instruments(str(mscz_path), midi_ref=mid_ref)

    out = ws / f"{stem}_clean.mscz"
    if out.exists(): out.unlink()
    print(f"\n── Layout + dynamics + style ──")
    cleanup_mscz(str(mscz_path), str(out))
    print(f"\nDone: {out.name}")
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description='MIDI/MSCZ → 整理后的 MSCZ')
    ap.add_argument('--mscz', type=str, help='直接处理 MSCZ（跳过 MIDI 量化）')
    ap.add_argument('--midi', type=str, help='指定 MIDI 文件')
    args = ap.parse_args()

    ws = Path(__file__).parent

    if args.mscz:
        pipeline_mscz(Path(args.mscz))
        return 0

    if args.midi:
        pipeline_midi(Path(args.midi))
        return 0

    # Auto-detect: prefer MIDI
    mids = [f for f in ws.glob('*.mid') if '_q.mid' not in f.name and '_quantized' not in f.name]
    if not mids: mids = list(ws.glob('*.mid'))
    if mids:
        for m in mids: pipeline_midi(m)
        return 0

    msczs = list(ws.glob('*.mscz'))
    if msczs:
        for m in msczs: pipeline_mscz(m)
        return 0

    print("No MIDI or MSCZ files found.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
