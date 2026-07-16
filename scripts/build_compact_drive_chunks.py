#!/usr/bin/env python3
import csv
from pathlib import Path
OUT=Path('data/green_gregory')
SRC=OUT/'sam_balanced_intake_100.csv'
DEST=OUT/'drive_compact_chunks'; DEST.mkdir(parents=True,exist_ok=True)
for p in DEST.glob('chunk_*.tsv'): p.unlink()
with SRC.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f)); headers=list(rows[0])
def clean(v,limit=None):
    s=(v or '').replace('\t',' ').replace('\r',' ').replace('\n',' ').strip()
    return s if limit is None or len(s)<=limit else s[:limit-1]+'…'
for i in range(10):
    lines=[]
    for r in rows[i*10:(i+1)*10]:
        vals=[]
        for h in headers:
            lim=700 if h=='Description' else 350 if h=='Notes' else 220 if h in {'Title','Historical Source URL','Award Notice URL'} else None
            vals.append(clean(r.get(h,''),lim))
        lines.append('\t'.join(vals))
    (DEST/f'chunk_{i+1:02d}.tsv').write_text('\n'.join(lines),encoding='utf-8')
print('chunks',10,'rows',len(rows),'columns',len(headers))
