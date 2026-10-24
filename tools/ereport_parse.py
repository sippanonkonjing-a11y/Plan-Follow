"""Parse Allianz Ayudhya 'FYP Submission and Paid Report by Group Manager' (PLN_RP7041) PDFs.
The PDF uses Type 3 fonts with no text mapping, so digits are identified by the shape of each glyph."""
import sys, re, json, hashlib, os
from pypdf import PdfReader
GLYPHS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glyphs.json')))

def runs(path):
    r = PdfReader(path); out = []; cache = {}
    for pi, pg in enumerate(r.pages):
        def v(text, cm, tm, fd, fs):
            if fd is None or not text.strip(): return
            key = fd.indirect_reference.idnum if fd.indirect_reference else id(fd)
            if key not in cache:
                cp = fd['/CharProcs'].get_object()
                cache[key] = {k: hashlib.md5(cp[k].get_object().get_data()).hexdigest()[:10] for k in cp}
            names = re.findall(r'/c\d+', text)
            s = ''.join(GLYPHS.get(cache[key].get(n, ''), '?') for n in names)
            out.append(dict(p=pi, x=round(tm[4] + cm[4]), y=round(tm[5] + cm[5]), s=s.strip()))
        pg.extract_text(visitor_text=v)
    return out

NUM = re.compile(r'^\d{1,3}(,\d{3})*(\.\d+)?$|^\.\d+$|^\d+$')
def num(s): return float(s.replace(',', '')) if s.startswith('.') or '.' in s else int(s.replace(',', ''))

def parse(path):
    R = runs(path); rows = []; totals = []
    lines = {}
    for r in R: lines.setdefault((r['p'], r['y']), []).append(r)
    for (p, y), rs in sorted(lines.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
        rs.sort(key=lambda r: r['x'])
        unit = next((r['s'] for r in rs if 50 <= r['x'] <= 90 and re.fullmatch(r'\d{6}', r['s'])), None)
        grp = next((r['s'] for r in rs if 90 < r['x'] <= 120 and re.fullmatch(r'\d{3}', r['s'])), None)
        if unit:
            toks = []
            for r in rs:
                if r['x'] < 370: continue
                parts = r['s'].split()
                # a run holding several values is only safe when they are identical (their order in the PDF is unreliable)
                if len(parts) > 1 and len(set(parts)) > 1:
                    raise ValueError(f'unit {unit}: mixed values in one text run {parts}')
                toks += parts
            if len(toks) != 7 or not all(NUM.match(t) for t in toks):
                raise ValueError(f'unit {unit}: expected 7 numbers, got {toks}')
            vals = [num(t) for t in toks]
            rows.append(dict(unit=unit, grp=grp, dF=vals[0], dC=vals[1], sF=vals[2], sC=vals[3], pF=vals[4], pC=vals[5], pc=round(vals[6], 2)))
        else:
            toks = [t for r in rs if r['x'] >= 370 for t in r['s'].split()]
            if len(toks) == 7 and all(NUM.match(t) for t in toks): totals.append([num(t) for t in toks])
    if not rows: raise ValueError('no unit rows found')
    groups = {r['grp'] for r in rows}
    if len(groups) != 1: raise ValueError(f'expected one group, got {groups}')
    calc = [round(sum(r[k] for r in rows), 2) for k in ('dF', 'dC', 'sF', 'sC', 'pF', 'pC', 'pc')]
    # total rows come out of the PDF in a scrambled order, so compare them as a set of values
    if not totals or sorted(round(t, 2) for t in totals[0]) != sorted(calc):
        raise ValueError(f'row sums {calc} do not match report total {totals[:1]}')
    m = re.search(r'_(\d{1,2})_(\d{4})(\d{2})(\d{2})\.pdf$', os.path.basename(path))
    asof = f'{m.group(2)}-{m.group(3)}-{int(m.group(1)):02d}' if m else None
    return dict(group=groups.pop(), asof=asof, rows=rows, total=calc)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(json.dumps(parse(p), ensure_ascii=False))
