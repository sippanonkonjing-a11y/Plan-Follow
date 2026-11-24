"""Read the six MOC PDFs (AL MOC, AGENT MOC, UM Promotion for groups 660 and 705) and
apply them to the decrypted app page.

Usage:
  python3 moc.py parse <dir-with-pdfs> <out.json>
  python3 moc.py diff  <app.html> <new.json>
  python3 moc.py apply <app.html> <new.json> <prev.json|-> <asof-label> <prev-label>
"""
import sys, re, json, glob, subprocess, os

NUM = r'-?[\d,]+(?:\.\d+)?'


def text(pdf):
    return subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout


def num(t):
    if t is None or t in ('ยกเว้น', '-', ''):
        return None
    v = float(t.replace(',', ''))
    return int(v) if v == int(v) and '.' not in t else v


def clean_name(raw):
    parts = [p.replace(' ', '') for p in re.split(r'\s{2,}', raw.strip()) if p.strip()]
    return ' '.join(parts).replace('ำา', 'ำ').replace('ํา', 'ำ')


def joined_lines(t):
    """pdftotext sometimes pushes a stray tone mark and the rest of a row onto the next line."""
    L = t.split('\n'); out = []
    for l in L:
        if out and re.match(r'^\s*[ั-๎]+\s{2,}\d', l) and re.match(r'^\s*\d{5,6}\s+\S', out[-1]) and not re.search(r'\d{6}\s+(660|705)\s', out[-1]):
            mark = l.strip()[0]
            out[-1] = out[-1].rstrip() + mark + '   ' + re.sub(r'^\s*[ั-๎]+', '', l)
        else:
            out.append(l)
    return out


def parse_al(t):
    rows = []
    for l in joined_lines(t):
        m = re.match(r'^\s*(\d{6})\s+(\d+)\s+(.+?)\s+([AH])\s+(\w+)\s+(660|705)\s+(\d{4}-\d{2}-\d{2})\s+(' + NUM + r')\s+(' + NUM + r')\s+(\d+)\s+(\d+)\s*$', l)
        if m:
            rows.append(dict(unit=m[1], code=m[2], name=clean_name(m[3]), st=m[4], pos=m[5], g=m[6], tg=num(m[8]), pc=num(m[9]), at=int(m[10]), an=int(m[11])))
    return rows


def parse_agents(t):
    rows = []
    for l in joined_lines(t):
        m = re.match(r'^\s*(\d{5,6})\s+(.+?)\s+(\d{6})\s+(660|705)\s+([AH])\s+(\w+)\s+(\d{4}-\d{2})-\d{2}\s+(.*)$', l)
        if not m:
            continue
        nums = re.findall(NUM + r'|ยกเว้น', m[8])
        vals = [num(x) for x in nums]
        if len(vals) == 4:
            t1, p1, t2, p2 = vals
        elif len(vals) == 3:
            t1 = None; p1, t2, p2 = vals
        else:
            raise SystemExit('cannot read agent row: ' + l)
        rows.append(dict(code=int(m[1]), name=clean_name(m[2]), unit=m[3], g=m[4], st=m[5], join=m[7], t1=t1, p1=p1 or 0, t2=t2, p2=p2 or 0))
    return rows


def parse_um(t):
    rows = {}
    for l in joined_lines(t):
        m = re.match(r'^\s*(\d{5,6})\s+(.+?)\s+(\d{6})\s+(660|705)\s+(\w+)\s+([AH])\s+\S+\s+(.*)$', l)
        if not m:
            continue
        toks = re.findall(NUM + r'|ยกเว้น', m[7])
        if len(toks) < 11:
            continue
        v = [num(x) for x in toks[:11]]
        rows[int(m[1])] = dict(oms6=v[0], oms12=v[1], own6=v[2], team6=v[3], tot6=v[4], c30_6=v[5], own12=v[6], team12=v[7], tot12=v[8], c30_12=v[9], per=v[10])
    return rows


def parse_dir(d):
    out = {}
    for g in ('705', '660'):
        f = lambda kind: [p for p in glob.glob(os.path.join(d, '*.pdf')) if kind in os.path.basename(p) and g in os.path.basename(p)]
        al, ag, um = f('AL_MOC'), f('AGENT_MOC'), f('UM_PROMOTION')
        assert len(al) == len(ag) == len(um) == 1, (g, al, ag, um)
        U = parse_al(text(al[0])); A = parse_agents(text(ag[0])); P = parse_um(text(um[0]))
        for a in A:
            p = P.get(a['code'])
            a['team'] = (p or {}).get('team12') or 0
            a['c30'] = (p or {}).get('c30_12') or 0
            a['per'] = (p or {}).get('per')
            a['gft'] = [p['own6'] or 0, p['team6'] or 0, p['c30_6'] or 0, p['own12'] or 0] if p else None
        out[g] = dict(units=U, agents=A)
        print(g, len(U), 'units', len(A), 'agents', sum(1 for a in A if a['gft'] is not None), 'with UM row', file=sys.stderr)
    return out


def js_agents(A):
    rows = sorted(A, key=lambda a: str(a['code']))
    return '[\n' + ',\n'.join(json.dumps([a['code'], a['name'], a['unit'], a['st'], a['join'], a['t1'], a['p1'], a['t2'], a['p2'], a['team'], a['c30'], a['per']], ensure_ascii=False, separators=(',', ':')) for a in rows) + ']'


def old_arrays(html):
    U = json.loads(re.search(r'const UNITS=(\[[\s\S]*?\]\]);', html)[1])
    A = {g: json.loads(re.search(r'const A' + g + r'=(\[[\s\S]*?\]\]);', html)[1]) for g in ('705', '660')}
    return U, A


def diff(html, new):
    U, A = old_arrays(html)
    ou = {u[0]: u for u in U}
    for g in ('705', '660'):
        for u in new[g]['units']:
            o = ou.get(u['unit'])
            if not o: print('NEW UNIT', u); continue
            if o[5] != u['pc'] or o[7] != u['an']:
                print(f"UNIT {g} {u['unit']} {o[1]}: PC {o[5]:,} -> {u['pc']:,} ({u['pc']-o[5]:+,}) agents {o[7]} -> {u['an']}")
        oa = {r[0]: r for r in A[g]}
        na = {a['code']: a for a in new[g]['agents']}
        for c, a in na.items():
            o = oa.get(c)
            if not o: print('NEW AGENT', g, c, a['name'], a['unit'], a['st'], a['join'], 'p2', a['p2']); continue
            ch = []
            for i, k in ((3, 'st'), (6, 'p1'), (8, 'p2'), (9, 'team'), (10, 'c30'), (11, 'per')):
                if o[i] != a[k]: ch.append(f'{k} {o[i]}->{a[k]}')
            if ch: print('AGENT', g, c, o[1], o[2], '; '.join(ch))
        for c in oa:
            if c not in na: print('REMOVED', g, c, oa[c][1])


def apply(html, new, prev, asof, prev_label):
    U, A = old_arrays(html)
    oldname = {u[0]: u[1] for u in U}
    for g in A:
        for r in A[g]: oldname[r[0]] = r[1]
    units = []
    for g in ('705', '660'):
        for u in new[g]['units']:
            units.append([u['unit'], oldname.get(u['unit'], u['name']), u['pos'], g, u['tg'], u['pc'], u['at'], u['an']])
    html = re.sub(r'const UNITS=\[[\s\S]*?\]\];', lambda m: 'const UNITS=[\n' + ',\n'.join(json.dumps(x, ensure_ascii=False, separators=(',', ':')) for x in units) + '];', html, count=1)
    gft = {}
    for g in ('705', '660'):
        for a in new[g]['agents']:
            a['name'] = oldname.get(a['code'], a['name'])
            if a['gft'] and a['gft'] != [a['p2'], 0, 0, a['p1'] + a['p2']]:
                gft[str(a['code'])] = a['gft']
        html = re.sub(r'const A' + g + r'=\[[\s\S]*?\]\];', lambda m: 'const A' + g + '=' + js_agents(new[g]['agents']) + ';', html, count=1)
    html, n = re.subn(r'const GFT=\{.*?\};', lambda m: 'const GFT=' + json.dumps(gft, separators=(',', ':')) + ';', html, count=1)
    assert n == 1
    if prev:
        pa = {str(r[0]): [r[8], r[9]] for g in A for r in A[g]}
        pu = {u[0]: u[5] for u in U}
        html = re.sub(r'const PREV_A=\{.*?\};', lambda m: 'const PREV_A=' + json.dumps(pa, separators=(',', ':')) + ';', html, count=1, flags=re.S)
        html = re.sub(r'const PREV_U=\{.*?\};', lambda m: 'const PREV_U=' + json.dumps(pu, separators=(',', ':')) + ';', html, count=1, flags=re.S)
        html = re.sub(r'const PREV_DATE="[^"]*";', 'const PREV_DATE="' + prev_label + '";', html, count=1)
    return html


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'parse':
        json.dump(parse_dir(sys.argv[2]), open(sys.argv[3], 'w'), ensure_ascii=False)
    elif cmd == 'diff':
        diff(open(sys.argv[2]).read(), json.load(open(sys.argv[3])))
    elif cmd == 'apply':
        h = apply(open(sys.argv[2]).read(), json.load(open(sys.argv[3])), sys.argv[4] != '-', sys.argv[5], sys.argv[6])
        open(sys.argv[2], 'w').write(h)
