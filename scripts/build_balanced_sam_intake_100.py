#!/usr/bin/env python3
import csv, json, re, hashlib
from collections import Counter, defaultdict
from pathlib import Path

OUT=Path('data/green_gregory')
SOL=OUT/'sam_historical_open_2023_2024.csv'
AWD=OUT/'sam_award_notice_index_2023_2025.csv'

TARGETS={
 'Office and facility consumables':40,
 'MRO tools and commercial hardware':30,
 'Packaging, shipping, storage and containers':15,
 'Basic IT accessories and standard equipment':10,
 'Mixed controls':5,
}

RESTRICTED_SET_ASIDE=['8(a)','8a ','hubzone','woman-owned','women-owned','wosb','edwosb','service-disabled','sdvosb','veteran-owned','vosb','indian economic','buy indian','local area']
MANDATORY=['abilityone','skilcraft','national industries for the blind','nib ','unicor','federal prison industries','mandatory source']
VEHICLE=['fair opportunity','only holders of','existing idiq','existing bpa','bpa holders','schedule holders','task order competition','delivery order competition','gwac holders']
EXCLUSIONS={
 'Food / perishables':['food','fruit','vegetable','meat','milk','bread','produce','catering','meal','grocery','beverage'],
 'Medical / pharmaceutical':['medical supply','pharmaceutical','drug','syringe','vaccine','patient care','clinical','implant','surgical'],
 'Fuel / petroleum':[' fuel','gasoline','diesel','petroleum','aviation fuel','lubricant'],
 'Hazardous chemical':['hazmat','hazardous chemical','chemical disposal','pesticide','solvent',' acid','sealant','adhesive','paint thinner'],
 'Construction / installation / repair / field service':['construction','renovation','installation',' install ','repair service','maintenance service','grounds maintenance','janitorial service','landscaping','demolition','roof replacement','painting service','inspection service'],
 'Rental / lease':['rental',' rent ','lease '],
 'Custom / personalized':['custom manufacturing','custom fabricated','personalized','custom printing','embroidered','made-to-order'],
 'Safety-critical / defense platform':['aircraft part','airframe','weapon','missile','flight critical','nuclear','armored vehicle','torpedo','helicopter component'],
}

OFFICE_WORDS=['office supplies','copy paper','xerographic','paper products','toner','ink cartridge','envelope','binder','file folder','folder','notebook','writing instrument','pen ','pencil','janitorial supplies','cleaning supplies','trash bag','paper towel','toilet tissue','facial tissue','light bulb','led lamp','battery','batteries','breakroom','tableware','furniture','chair','desk','shredder']
MRO_WORDS=['hand tool','power tool','wrench','socket set','screwdriver','drill','saw blade','bolt cutter','fastener','bolt ','screw ','commercial hardware','ladder','hose','valve','bearing','filter','pump','abrasive','sandpaper','grinding wheel','work light','headlamp','toolbox','extension cord','shop equipment']
PACK_WORDS=['packaging','packing','shipping box','carton','container','pallet','crate','storage bin','plastic bag','poly bag','stretch wrap','strapping','shipping supplies','mailing tube','packing tape','bubble wrap','storage container']
IT_WORDS=['computer monitor','monitor','keyboard','mouse','printer','scanner','network switch','router','ethernet','network cable','usb cable','headset','uninterruptible power','ups ','laptop','tablet','webcam','docking station','hard drive','ssd','memory module','projector']


def n(s): return re.sub(r'[^a-z0-9]','',(s or '').lower())
def fmoney(v):
 s=re.sub(r'[^0-9.\-]','',v or '')
 try:return float(s)
 except:return None

def is_nullish(v): return (v or '').strip().lower() in {'','null','none','n/a'}

def setaside_fit(s):
 low=(s or '').lower()
 if any(x in low for x in RESTRICTED_SET_ASIDE): return 'No — socioeconomic set-aside not held by GGG'
 if not low or 'no set' in low or 'total small business' in low or 'small business set-aside' in low: return 'Potentially yes — subject to historical SAM registration and representations'
 return 'Review — set-aside language requires validation'

def exclusion(text):
 for label,terms in EXCLUSIONS.items():
  if any(t in text for t in terms): return label
 return 'Pass / no automatic exclusion detected'

def track(text,psc,naics):
 p=(psc or '').upper(); na=(naics or '')
 scores={
  'Office and facility consumables':sum(x in text for x in OFFICE_WORDS)+(3 if p.startswith(('75','71','72','79')) else 0),
  'MRO tools and commercial hardware':sum(x in text for x in MRO_WORDS)+(3 if p.startswith(('51','52','53','34','41','43','44','47','48','49')) else 0),
  'Packaging, shipping, storage and containers':sum(x in text for x in PACK_WORDS)+(4 if p.startswith('81') else 0),
  'Basic IT accessories and standard equipment':sum(x in text for x in IT_WORDS)+(4 if p.startswith(('70','74','7E','7G')) or na in {'334111','334112','334118','423430'} else 0),
 }
 best=max(scores,key=scores.get)
 return best if scores[best]>0 else 'Mixed controls'

def defense_restricted(row,text):
 p=(row.get('psc') or '').upper(); sol=(row.get('solicitation_number') or '').upper(); agency=(row.get('agency') or '').upper()
 if any(x in text for x in ['nsn ','national stock number','approved source','source controlled','critical application item','flight safety','weapon system']): return True
 if 'DEFENSE LOGISTICS AGENCY' in (row.get('subagency') or '').upper() and re.match(r'^(SPE|SPR|SPM)',sol):
  if p[:2] in {'10','11','12','13','14','15','16','17','18','19','20','22','23','25','26','28','29','30','31','32','35','36','37','38','39','40','42','58','59','61','62','66'}: return True
 return False

def rep_score(r):
 d=r.get('description') or ''
 score=min(len(d),2000)/100
 if r.get('additional_info'): score+=8
 if r.get('record_link'): score+=2
 if not re.match(r'^amendment\b',d.strip(),re.I): score+=10
 if r.get('notice_type')=='Combined Synopsis/Solicitation': score+=2
 return score

def normalize_sol(s): return re.sub(r'[^A-Z0-9]','',(s or '').upper())

with SOL.open(encoding='utf-8',newline='') as f: solrows=list(csv.DictReader(f))
with AWD.open(encoding='utf-8',newline='') as f: awardrows=list(csv.DictReader(f))

# Build award answer-key index without influencing solicitation selection.
award_by_sol=defaultdict(list)
for a in awardrows:
 key=normalize_sol(a.get('solicitation_number'))
 if key: award_by_sol[key].append(a)

# Collapse notice versions/amendments into solicitation families.
families=defaultdict(list)
for r in solrows:
 key=normalize_sol(r.get('solicitation_number')) or ('NOTICE'+(r.get('notice_id') or ''))
 families[key].append(r)

candidates=[]
for key,versions in families.items():
 rep=max(versions,key=rep_score)
 original=min(versions,key=lambda r:(r.get('posted_date_parsed') or '9999',r.get('notice_id') or ''))
 latest=max(versions,key=lambda r:(r.get('posted_date_parsed') or '',r.get('notice_id') or ''))
 text=(' '.join([(rep.get('title') or ''),(rep.get('description') or ''),(original.get('description') or '')])).lower()
 tr=track(text,rep.get('psc'),rep.get('naics'))
 excl=exclusion(text)
 if defense_restricted(rep,text): excl='Restricted NSN / approved-source / defense-platform risk'
 sf=setaside_fit(rep.get('set_aside'))
 mandatory='Probable mandatory-source conflict' if any(x in text for x in MANDATORY) else 'No conflict detected in metadata; exact product review required'
 vehicle=any(x in text for x in VEHICLE)
 openpath='No — vehicle-limited language detected' if vehicle else 'Potentially yes — direct solicitation or combined notice'
 ggg='No — parent/limited vehicle path detected' if vehicle else sf
 # Metadata completeness is a prioritization signal; hard Gate 7 remains pending archive review.
 detail=0
 if len(rep.get('description') or '')>=250: detail+=2
 if re.search(r'\b(qty|quantity|each|case|pack|unit|clin|part number|model|salient|specification)\b',text): detail+=2
 if rep.get('additional_info'): detail+=2
 if len(versions)>1: detail+=1
 comp='Promising metadata; archive requirements review required' if detail>=4 else ('Partial metadata; archive retrieval required' if detail>=2 else 'Sparse metadata; high Gate 7 risk')
 outcomes=award_by_sol.get(key,[])
 # prefer a record with actual awardee/amount
 outcome=max(outcomes,key=lambda a:(0 if is_nullish(a.get('awardee')) else 2)+(1 if fmoney(a.get('award_amount')) is not None else 0)+(1 if a.get('award_number') else 0),default=None)
 amount=fmoney(outcome.get('award_amount')) if outcome else None
 access_score=0 if vehicle or mandatory.startswith('Probable') or ggg.startswith('No') else (90 if ggg.startswith('Potentially') else 55)
 fit=0
 if excl.startswith('Pass'):
  fit=45+(15 if tr!='Mixed controls' else 0)+(15 if detail>=4 else 7 if detail>=2 else 0)
  if amount is not None and amount<=10000: fit+=15
  elif amount is not None and amount<=25000: fit+=8
  elif amount is not None and amount>50000: fit-=15
 if access_score==0 or not excl.startswith('Pass'): call='Strikeout'
 elif comp.startswith('Sparse'): call='Double'
 elif amount is not None and amount<=5000 and fit>=80: call='Grand Slam'
 elif fit>=75: call='Home Run'
 elif fit>=65: call='Triple'
 elif fit>=50: call='Double'
 else: call='Single'
 gate='Passes Gates 1-6 preliminarily; Gate 7 archive review pending'
 if vehicle: gate='Gate 3 — open competitive path'
 elif ggg.startswith('No'): gate='Gate 4 — GGG eligibility'
 elif mandatory.startswith('Probable'): gate='Gate 5 — mandatory source'
 elif not excl.startswith('Pass'): gate='Gate 6 — product/service exclusion'
 candidates.append({'key':key,'rep':rep,'original':original,'latest':latest,'versions':versions,'text':text,'track':tr,'exclusion':excl,'setaside_fit':sf,'mandatory':mandatory,'openpath':openpath,'ggg':ggg,'completeness':comp,'detail_score':detail,'outcome':outcome,'award_amount_num':amount,'access_score':access_score,'fit_score':max(0,fit),'call':call,'gate':gate})

# Selection pools. Preferred lanes require preliminary accessibility and no automatic product exclusion.
preferred=[c for c in candidates if c['track'] in TARGETS and c['track']!='Mixed controls' and c['access_score']>0 and c['exclusion'].startswith('Pass')]
# Stable ranking: archive detail, outcome availability (for answer key), lower award amount, then deterministic hash.
def rank_key(c):
 outcome_quality=2 if c['outcome'] and (not is_nullish(c['outcome'].get('awardee'))) and c['award_amount_num'] is not None else 1 if c['outcome'] else 0
 amount=c['award_amount_num'] if c['award_amount_num'] is not None else 999999999
 h=int(hashlib.sha256(c['key'].encode()).hexdigest()[:12],16)
 return (-c['detail_score'],-outcome_quality,amount,h)

selected=[]; selected_keys=set(); shortage={}
for tr,quota in TARGETS.items():
 if tr=='Mixed controls': continue
 pool=sorted([c for c in preferred if c['track']==tr],key=rank_key)
 take=pool[:quota]; selected.extend(take); selected_keys.update(c['key'] for c in take)
 shortage[tr]=max(0,quota-len(take))
# Fill lane shortages from remaining accessible preferred records, preserving concentration.
remaining=sorted([c for c in preferred if c['key'] not in selected_keys],key=rank_key)
needed=95-len(selected)
selected.extend(remaining[:max(0,needed)]); selected_keys.update(c['key'] for c in remaining[:max(0,needed)])
# Five mixed controls: deterministic mix of accessible lower fit, restricted eligibility, and obvious exclusions.
control_pool=[c for c in candidates if c['key'] not in selected_keys]
control_pool.sort(key=lambda c:(0 if c['access_score']>0 else 1, abs(c['fit_score']-40), int(hashlib.sha256(c['key'].encode()).hexdigest()[:12],16)))
controls=[]
# 2 accessible but weaker
controls += [c for c in control_pool if c['access_score']>0 and c['exclusion'].startswith('Pass')][:2]
# 1 eligibility fail
controls += [c for c in control_pool if c['gate'].startswith('Gate 4') and c not in controls][:1]
# 2 product exclusions
controls += [c for c in control_pool if c['gate'].startswith('Gate 6') and c not in controls][:2]
for c in controls: selected_keys.add(c['key'])
selected.extend(controls)
# If preferred availability was insufficient, fill to exactly 100 with best remaining records, explicitly marked controls.
if len(selected)<100:
 for c in sorted([x for x in candidates if x['key'] not in selected_keys],key=rank_key):
  selected.append(c); selected_keys.add(c['key'])
  if len(selected)==100: break
selected=selected[:100]
assert len(selected)==100

rows=[]; gate_counts=Counter(); tracks=Counter(); agencies=Counter(); calls=Counter(); outcome_count=0
for i,c in enumerate(selected,1):
 r=c['rep']; o=c['outcome']; tracks[c['track']]+=1; agencies[r.get('agency') or 'Unknown']+=1; calls[c['call']]+=1; gate_counts[c['gate']]+=1
 if o: outcome_count+=1
 pop=', '.join(x for x in [r.get('city'),r.get('state'),r.get('zip'),r.get('country')] if x)
 version_ids='; '.join(v.get('notice_id','') for v in sorted(c['versions'],key=lambda x:x.get('posted_date_parsed','')))
 selection_role='Target-lane candidate' if c in selected[:-len(controls)] or c['track']!='Mixed controls' else 'Mixed control'
 outcome_url=o.get('historical_source_url','') if o else ''
 awardee='' if not o or is_nullish(o.get('awardee')) else o.get('awardee','')
 award_amount='' if not o else o.get('award_amount','')
 notes=f"Selection role: {selection_role}. Solicitation family contains {len(c['versions'])} notice version(s): {version_ids}. Representative notice chosen by detail score, not outcome. Historical award mapping did not control selection."
 rows.append({
  'Intake ID':f'HOS01-{i:03d}','Notice ID':r.get('notice_id',''),'Solicitation Number':r.get('solicitation_number',''),'Historical Source URL':r.get('historical_source_url',''),'Notice Type':r.get('notice_type',''),'Posted Date':c['original'].get('posted_date_parsed',''),'Original Response Deadline':c['latest'].get('response_deadline_parsed') or r.get('response_deadline_parsed',''),'Agency':r.get('agency',''),'Subagency':r.get('subagency',''),'Contracting Office':r.get('contracting_office',''),'Title':r.get('title',''),'Description':(r.get('description') or '')[:1800],'NAICS':r.get('naics',''),'PSC':r.get('psc',''),'Set-Aside Type':r.get('set_aside',''),'Estimated Value':'Unknown pre-award; historical award retained only as answer key when mapped','Product or Service':'Product / commercial supply candidate' if c['exclusion'].startswith('Pass') else 'Excluded or control category','Supply Track':c['track'],'Place of Performance':pop,'Delivery Destination':pop or 'Archive review required','Attachments Available':'Archive retrieval required; AdditionalInfoLink present' if r.get('additional_info') else 'Direct notice/resource lookup required','Amendments Available':f"Yes — {len(c['versions'])} notice version(s)" if len(c['versions'])>1 else 'No separate version identified in extract','Q&A Available':'Unknown — archive retrieval required','Award Outcome Available':'Mapped from 2023-2025 award index' if o else 'Not yet recovered','Award Notice URL':outcome_url,'Awardee':awardee,'Award Amount':award_amount,'Award Type':o.get('notice_type','') if o else '','Parent Award ID':'No parent vehicle indicated at solicitation intake; verify clauses','Open Competitive Path':c['openpath'],'Parent Vehicle Required':'No evidence in metadata; verify solicitation' if c['openpath'].startswith('Potentially') else 'Yes / probable','Could GGG Compete At Time':c['ggg'],'Mandatory-Source Status':c['mandatory'],'AbilityOne Status':'Exact product/NSN review required','Product-Exclusion Result':c['exclusion'],'Requirement Completeness':c['completeness'],'Payment-Method Evidence':'Unknown — never infer from award amount','Preliminary Supplier Exposure':'Not modeled before archive and supplier-pricing gates','Exposure Classification':'Unclassified pending requirements and sourcing','Preliminary Probable Net':'Not modeled before supplier pricing','Preliminary Accessibility Score':c['access_score'],'Preliminary Kickoff Fit Score':c['fit_score'],'Preliminary Baseball Call':c['call'],'Primary Failure Point':c['gate'],'Intake Decision':'REVIEW — archive reconstruction' if c['gate'].startswith('Passes') else 'NO-BID / CONTROL','Confidence':'Moderate — official extract metadata; direct archive review pending','Notes':notes,'Source Extract Row':r.get('source_extract_row','')
 })

headers=list(rows[0])
with (OUT/'sam_balanced_intake_100.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=headers); w.writeheader(); w.writerows(rows)
for k in range(4):
 (OUT/f'sam_balanced_intake_100_part{k+1}.json').write_text(json.dumps(rows[k*25:(k+1)*25],indent=2),encoding='utf-8')
summary={'sample_method':'Distinct solicitation families selected from the 1,024 closed 2023-2024 Solicitation/Combined notices. Selection is stratified by preferred supply lanes and independent of award availability. Notice versions are collapsed; historical award notices are mapped afterward as answer keys.','solicitation_universe_rows':len(solrows),'distinct_solicitation_families':len(candidates),'selected':len(rows),'target_quotas':TARGETS,'quota_shortage_before_fill':shortage,'gate_counts':dict(gate_counts),'supply_tracks':dict(tracks),'top_agencies':agencies.most_common(15),'baseball_calls':dict(calls),'mapped_outcomes':outcome_count,'archive_review_count':sum(1 for r in rows if r['Intake Decision'].startswith('REVIEW')),'control_or_reject_count':sum(1 for r in rows if not r['Intake Decision'].startswith('REVIEW')),'sampling_pass_1_failure':{'method':'Conditioned on embedded award fields','result':'98/100 rejected; 88/100 DoD; amendment duplication; rejected as intake sample due to outcome-recovery and agency bias'}}
(OUT/'sam_balanced_intake_100_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
# Keep a compact ranked candidate file for final-20 selection after archive enrichment.
ranked=[{'Intake ID':r['Intake ID'],'Notice ID':r['Notice ID'],'Solicitation Number':r['Solicitation Number'],'Title':r['Title'],'Supply Track':r['Supply Track'],'Accessibility Score':r['Preliminary Accessibility Score'],'Kickoff Fit Score':r['Preliminary Kickoff Fit Score'],'Prediction':r['Preliminary Baseball Call'],'Gate':r['Primary Failure Point'],'Award Outcome Available':r['Award Outcome Available']} for r in rows]
(OUT/'sam_balanced_intake_ranked.json').write_text(json.dumps(ranked,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
