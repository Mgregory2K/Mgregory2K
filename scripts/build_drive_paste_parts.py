#!/usr/bin/env python3
import csv, json
from pathlib import Path

OUT=Path('data/green_gregory')
SRC=OUT/'sam_balanced_intake_100.csv'
PARTS=OUT/'drive_paste_parts'
PARTS.mkdir(parents=True,exist_ok=True)
with SRC.open(encoding='utf-8',newline='') as f:
    rows=list(csv.reader(f))
header, data=rows[0],rows[1:]

def clean(v):
    return (v or '').replace('\t',' ').replace('\r',' ').replace('\n',' ').strip()
for i in range(20):
    part=data[i*5:(i+1)*5]
    text='\n'.join('\t'.join(clean(v) for v in row) for row in part)
    (PARTS/f'intake_part_{i+1:02d}.tsv').write_text(text,encoding='utf-8')
summary=json.loads((OUT/'sam_balanced_intake_100_summary.json').read_text(encoding='utf-8'))
funnel=[
 ['Stage / Metric','Count','Interpretation'],
 ['Official SAM full extract rows','78811','Source population at retrieval'],
 ['Posted during 2023-2024','5739','Primary historical period'],
 ['Actual Solicitation or Combined notice','1505','Notice-type gate'],
 ['Response deadline no later than 2024-12-31','1024','Closed historical solicitation universe'],
 ['Distinct solicitation families',str(summary['distinct_solicitation_families']),'Amendments and notice versions collapsed'],
 ['Balanced intake selected','100','Selection independent of award outcome'],
 ['Pass Gates 1-6 preliminarily',str(summary['gate_counts'].get('Passes Gates 1-6 preliminarily; Gate 7 archive review pending',0)),'Advance to archive/attachment review'],
 ['Killed at Gate 4 — GGG eligibility',str(summary['gate_counts'].get('Gate 4 — GGG eligibility',0)),'Set-aside or eligibility mismatch'],
 ['Killed at Gate 5 — mandatory source',str(summary['gate_counts'].get('Gate 5 — mandatory source',0)),'Mandatory-channel signal'],
 ['Killed at Gate 6 — product/service exclusion',str(summary['gate_counts'].get('Gate 6 — product/service exclusion',0)),'Current kickoff exclusions'],
 ['Award outcomes mapped at intake',str(summary['mapped_outcomes']),'Answer keys recovered without driving selection'],
 ['Sampling Pass 1 review count','2','Rejected outcome-conditioned sample'],
 ['Sampling Pass 1 rejection count','98','88/100 DoD; amendment and outcome bias'],
]
(PARTS/'funnel.tsv').write_text('\n'.join('\t'.join(r) for r in funnel),encoding='utf-8')
tracks=[['Supply Track','Selected Count','Target','Shortage Before Fill']]
for tr,count in summary['supply_tracks'].items():
    tracks.append([tr,str(count),str(summary['target_quotas'].get(tr,'')),str(summary['quota_shortage_before_fill'].get(tr,''))])
(PARTS/'tracks.tsv').write_text('\n'.join('\t'.join(r) for r in tracks),encoding='utf-8')
print(PARTS)
