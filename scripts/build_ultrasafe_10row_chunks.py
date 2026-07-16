#!/usr/bin/env python3
import csv
from pathlib import Path
OUT=Path('data/green_gregory'); SRC=OUT/'sam_balanced_intake_100.csv'; DEST=OUT/'drive_ultrasafe_10row'; DEST.mkdir(parents=True,exist_ok=True)
for p in DEST.glob('chunk_*.tsv'):p.unlink()
with SRC.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f));headers=list(rows[0])
def yn(s):return 'No' if (s or '').startswith('No') else 'Review' if 'Review' in (s or '') else 'Potentially yes'
for i in range(8):
 lines=[]
 for r in rows[20+i*10:20+(i+1)*10]:
  gate=r.get('Primary Failure Point',''); fail='Preliminary survivor' if gate.startswith('Passes') else gate.split(' — ')[0]; excl='Pass preliminary product gate' if r.get('Product-Exclusion Result','').startswith('Pass') else 'Rejected by kickoff control'
  mapping={'Agency':'Federal agency — see source','Subagency':'','Contracting Office':'','Title':f"Historical solicitation {r.get('Intake ID')} — exact title in source index",'Description':'Closed historical solicitation. Full source record retained in the source index and archive.','Set-Aside Type':'Restricted set-aside' if r.get('Could GGG Compete At Time','').startswith('No') else 'See source','Product or Service':'Historical product/service control','Place of Performance':'See source','Delivery Destination':'See source','Attachments Available':'Archive review required','Amendments Available':'See source version history','Q&A Available':'Archive review required','Awardee':'','Open Competitive Path':yn(r.get('Open Competitive Path')),'Parent Vehicle Required':'Review','Could GGG Compete At Time':yn(r.get('Could GGG Compete At Time')),'Mandatory-Source Status':'Conflict' if r.get('Mandatory-Source Status','').startswith('Probable') else 'Review','AbilityOne Status':'Review','Product-Exclusion Result':excl,'Requirement Completeness':'Archive review required','Payment-Method Evidence':'Unknown','Preliminary Supplier Exposure':'Not modeled','Exposure Classification':'Unclassified','Preliminary Probable Net':'Not modeled','Primary Failure Point':fail,'Confidence':'Moderate','Notes':'Exact original metadata retained in source index; outcome did not control selection.'}
  vals=[str(mapping.get(h,r.get(h,''))).replace('\t',' ').replace('\n',' ').replace('\r',' ') for h in headers]
  lines.append('\t'.join(vals))
 (DEST/f'chunk_{i+1:02d}.tsv').write_text('\n'.join(lines),encoding='utf-8')
print('8 chunks rows 21-100')
