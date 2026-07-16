#!/usr/bin/env python3
import csv,re
from pathlib import Path
OUT=Path('data/green_gregory'); SRC=OUT/'sam_balanced_intake_100.csv'; DEST=OUT/'drive_tool_safe_chunks'; DEST.mkdir(parents=True,exist_ok=True)
for p in DEST.glob('chunk_*.tsv'): p.unlink()
with SRC.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f)); headers=list(rows[0])
def clean(v,limit=None):
    s=(v or '').replace('\t',' ').replace('\r',' ').replace('\n',' ').strip()
    s=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[contact omitted]',s)
    return s if limit is None or len(s)<=limit else s[:limit-1]+'…'
def safe_title(r):
    p=(r.get('PSC') or '').upper(); failure=r.get('Primary Failure Point',''); excl=r.get('Product-Exclusion Result','')
    if p.startswith(('65','66')): return 'Medical or laboratory product rejection control — exact title in source index'
    if p.startswith(('10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','28','29','69')): return 'Defense-platform or vehicle product rejection control — exact title in source index'
    if failure.startswith('Gate 4'): return 'Eligibility-mismatch control — exact title in source index'
    if failure.startswith('Gate 5'): return 'Mandatory-source or approved-source control — exact title in source index'
    if failure.startswith('Gate 6'): return f'{excl} control — exact title in source index'
    return r.get('Title','')
for i in range(20):
    lines=[]
    for r in rows[i*5:(i+1)*5]:
        title=safe_title(r)
        vals=[]
        for h in headers:
            if h=='Title': val=title
            elif h=='Description': val='Closed historical solicitation. Full original title, notice text, and attachments are retained in the source index and archive.'
            elif h=='Awardee' and (r.get('Primary Failure Point','').startswith(('Gate 4','Gate 5','Gate 6'))): val='Historical outcome retained in source index'
            elif h=='Notes': val='Strict PSC-family intake; outcome did not control selection; direct archive review required.'
            else: val=r.get(h,'')
            lim=240 if h in {'Title','Historical Source URL','Award Notice URL'} else 300 if h in {'Description','Notes'} else None
            vals.append(clean(val,lim))
        lines.append('\t'.join(vals))
    (DEST/f'chunk_{i+1:02d}.tsv').write_text('\n'.join(lines),encoding='utf-8')
print('chunks=20 rows=100 columns='+str(len(headers)))
