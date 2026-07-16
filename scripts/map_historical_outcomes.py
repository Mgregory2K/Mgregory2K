#!/usr/bin/env python3
import csv, json, re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUT=Path('data/green_gregory')
INTAKE=OUT/'sam_balanced_intake_100.csv'
AWARDS=OUT/'sam_award_notice_index_2022_2025.csv'
DEST=OUT/'sam_historical_outcome_map_100.csv'

def norm(s): return re.sub(r'[^A-Z0-9]','',(s or '').upper())
def d(v):
    try:return datetime.strptime((v or '')[:10],'%Y-%m-%d').date()
    except:return None
def null(v):return (v or '').strip().lower() in {'','null','none','n/a'}
STOP={'THE','A','AN','AND','OR','OF','FOR','TO','IN','ON','WITH','FROM','AT','BY','SOLICITATION','AMENDMENT','COMBINED','SYNOPSIS','REQUEST','QUOTE','RFQ','RFP','SUPPLY','SUPPLIES','SERVICE','SERVICES'}
def tokens(s): return {x for x in re.findall(r'[A-Z0-9]{3,}',(s or '').upper()) if x not in STOP}
def jacc(a,b):
    if not a or not b:return 0
    return len(a&b)/len(a|b)
def base_sol(s):
    x=norm(s)
    x=re.sub(r'(AMENDMENT|AMEND|MOD|UPDATE|REVISION|REV|QSE)$','',x)
    x=re.sub(r'(_?\d+)$','',x) if '_' in (s or '') else x
    return x

with INTAKE.open(encoding='utf-8',newline='') as f:intake=list(csv.DictReader(f))
with AWARDS.open(encoding='utf-8',newline='') as f:awards=list(csv.DictReader(f))
exact=defaultdict(list); base=defaultdict(list); agency=defaultdict(list)
for a in awards:
    sk=norm(a.get('solicitation_number')); bk=base_sol(a.get('solicitation_number'))
    if sk:exact[sk].append(a)
    if bk:base[bk].append(a)
    agency[norm(a.get('agency'))].append(a)

rows=[]
for r in intake:
    sk=norm(r.get('Solicitation Number')); bk=base_sol(r.get('Solicitation Number'))
    posted=d(r.get('Posted Date')); deadline=d(r.get('Original Response Deadline'))
    methods=[]; pool=[]
    if sk and exact.get(sk):pool=exact[sk];methods=['Exact solicitation number']
    elif bk and base.get(bk):pool=base[bk];methods=['Normalized solicitation family']
    else: pool=agency.get(norm(r.get('Agency')),[]);methods=['Agency/title/date candidate search']
    rt=tokens(r.get('Title')); best=None; best_score=-1; reason=''
    for a in pool:
        ad=d(a.get('award_date_parsed') or a.get('award_date') or a.get('posted_date_parsed'))
        if deadline and ad and ad < deadline: continue
        if posted and ad and (ad-posted).days>730: continue
        at=tokens(a.get('title')); sim=jacc(rt,at)
        sol_exact=1 if sk and norm(a.get('solicitation_number'))==sk else 0
        sol_base=1 if bk and base_sol(a.get('solicitation_number'))==bk else 0
        sub=1 if norm(r.get('Subagency')) and norm(r.get('Subagency'))==norm(a.get('subagency')) else 0
        outcome=1 if (not null(a.get('awardee')) or not null(a.get('award_amount')) or a.get('award_number')) else 0
        score=100*sol_exact+70*sol_base+25*sim+5*sub+5*outcome
        if score>best_score:
            best_score=score;best=a;reason=f'sol_exact={sol_exact}; sol_base={sol_base}; title_similarity={sim:.3f}; subagency={sub}; outcome_fields={outcome}'
    confidence='Unresolved'; accepted=False
    if best:
        if best_score>=100:confidence='High';accepted=True
        elif best_score>=72:confidence='Moderate';accepted=True
        elif best_score>=24 and jacc(rt,tokens(best.get('title')))>=0.70:confidence='Moderate';accepted=True
        elif best_score>=18 and jacc(rt,tokens(best.get('title')))>=0.55:confidence='Low — manual verification required'
    rows.append({
        'Intake ID':r.get('Intake ID'),'Notice ID':r.get('Notice ID'),'Solicitation Number':r.get('Solicitation Number'),'Solicitation Title':r.get('Title'),
        'Mapping Method':methods[0] if methods else '','Outcome Mapped':'Yes' if accepted else 'No','Mapping Confidence':confidence,'Mapping Score':round(best_score,3) if best else '',
        'Mapping Evidence':reason if best else 'No candidate','Award Notice ID':best.get('notice_id','') if accepted else '','Award Notice URL':best.get('historical_source_url','') if accepted else '',
        'Award Number':best.get('award_number','') if accepted else '','Awardee':'' if not accepted or null(best.get('awardee')) else best.get('awardee',''),
        'Award Amount':'' if not accepted or null(best.get('award_amount')) else best.get('award_amount',''),'Award Date':best.get('award_date_parsed') or best.get('award_date','') if accepted else '',
        'Award Notice Type':best.get('notice_type','') if accepted else '','Outcome Notes':'Outcome map is an answer key only; it did not control intake selection.' if accepted else 'Replace final-20 candidate unless outcome can be manually recovered.'
    })
with DEST.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={'total':len(rows),'mapped_high':sum(x['Mapping Confidence']=='High' for x in rows),'mapped_moderate':sum(x['Mapping Confidence']=='Moderate' for x in rows),'mapped_low_review':sum(x['Mapping Confidence'].startswith('Low') for x in rows),'unresolved':sum(x['Outcome Mapped']=='No' for x in rows)}
(OUT/'sam_historical_outcome_map_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
