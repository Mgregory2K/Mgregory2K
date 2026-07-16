#!/usr/bin/env python3
import csv,re
from pathlib import Path
OUT=Path('data/green_gregory'); SRC=OUT/'sam_balanced_intake_100.csv'; DEST=OUT/'drive_sanitized_chunks'; DEST.mkdir(parents=True,exist_ok=True)
for p in DEST.glob('chunk_*.tsv'): p.unlink()
with SRC.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f)); headers=list(rows[0])
def clean(v,limit=None):
    s=(v or '').replace('\t',' ').replace('\r',' ').replace('\n',' ').strip()
    s=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[contact omitted]',s)
    return s if limit is None or len(s)<=limit else s[:limit-1]+'…'
for i in range(20):
    lines=[]
    for r in rows[i*5:(i+1)*5]:
        vals=[]
        for h in headers:
            if h=='Description': val=f"{r.get('Title','')} — closed historical solicitation. Full notice text and attachments are retained in the source archive."
            elif h=='Notes': val='Strict PSC-family intake; outcome did not control selection; direct archive review required.'
            else: val=r.get(h,'')
            lim=240 if h in {'Title','Historical Source URL','Award Notice URL'} else 320 if h in {'Description','Notes'} else None
            vals.append(clean(val,lim))
        lines.append('\t'.join(vals))
    (DEST/f'chunk_{i+1:02d}.tsv').write_text('\n'.join(lines),encoding='utf-8')
print('chunks=20 rows=100 columns='+str(len(headers)))
