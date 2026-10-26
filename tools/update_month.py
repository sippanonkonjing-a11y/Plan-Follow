"""Decrypt reports in inbox/, parse them, and write the month data into the decrypted app page.
Usage: python update_month.py <decrypted app.html>   (APP_PASSWORD in the environment)"""
import sys, os, re, json, glob, tempfile, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pfcrypt, ereport_parse

app = sys.argv[1]; pw = os.environ['APP_PASSWORD']
html = open(app, encoding='utf-8').read()
m = re.search(r'/\*MONTH_DATA_START\*/\s*const MONTH=(.*?);\s*/\*MONTH_DATA_END\*/', html, re.S)
if not m: sys.exit('month data markers not found in the app page')
month = json.loads(m.group(1))
HRE = r'/\*HIST_DATA_START\*/\s*const HIST=(.*?);\s*/\*HIST_DATA_END\*/'
hm = re.search(HRE, html, re.S)
hist = json.loads(hm.group(1)) if hm else None
hist_changed = False

done, changed = [], False
for f in sorted(glob.glob('inbox/*.bin')):
    with tempfile.TemporaryDirectory() as td:
        name = os.path.basename(f)[:-4]
        if not name.lower().endswith('.pdf'): name += '.pdf'
        pdf = os.path.join(td, name)
        open(pdf, 'wb').write(pfcrypt.decrypt(open(f, 'rb').read(), pw))
        d = ereport_parse.parse(pdf)
    if hist is not None and d['asof']:
        # daily history per group: date -> [PC, cases sent, cases approved, FYP sent, FYP approved, {unit: PC}]
        t = d['total']
        hist.setdefault(d['group'], {})[d['asof']] = [round(t[6], 2), t[3], t[5], t[2], t[4], {r['unit']: round(r['pc'], 2) for r in d['rows']}]
        hist[d['group']] = dict(sorted(hist[d['group']].items())[-150:])
        hist_changed = True
    old = month.get(d['group'])
    if old and old.get('asof') and d['asof'] and d['asof'] < old['asof']:
        print(f'{f}: older than current data for group {d["group"]} ({d["asof"]} < {old["asof"]}), skipped')
    else:
        month[d['group']] = {'asof': d['asof'], 'rows': [[r['unit'], r['dF'], r['dC'], r['sF'], r['sC'], r['pF'], r['pC'], r['pc']] for r in d['rows']], 'total': d['total'],
                              'upd': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime('%Y-%m-%dT%H:%M')}
        changed = True
        print(f'{f}: group {d["group"]} as of {d["asof"]}, {len(d["rows"])} units, PC {d["total"][6]:,.2f}')
    done.append(f)

if changed:
    # drop groups still showing an earlier month than the newest report
    newest = max(v['asof'][:7] for v in month.values() if v.get('asof'))
    for g in [g for g, v in month.items() if v.get('asof', '')[:7] < newest]:
        print(f'group {g} is from an earlier month, removed until its new report arrives'); del month[g]
    block = '/*MONTH_DATA_START*/\nconst MONTH=' + json.dumps(month, ensure_ascii=False, separators=(',', ':')) + ';\n/*MONTH_DATA_END*/'
    html = html[:m.start()] + block + html[m.end():]
if hist_changed:
    hm = re.search(HRE, html, re.S)
    html = html[:hm.start()] + '/*HIST_DATA_START*/\nconst HIST=' + json.dumps(hist, ensure_ascii=False, separators=(',', ':')) + ';\n/*HIST_DATA_END*/' + html[hm.end():]
    changed = True
if changed:
    open(app, 'w', encoding='utf-8').write(html)
open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a').write(f'changed={"true" if changed else "false"}\nprocessed={" ".join(done)}\n')
