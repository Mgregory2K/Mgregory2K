#!/usr/bin/env python3
import csv,json,re,hashlib
from collections import Counter,defaultdict
from pathlib import Path
OUT=Path('data/green_gregory'); SOL=OUT/'sam_historical_open_2022_2024.csv'; AWD=OUT/'sam_award_notice_index_2022_2025.csv'
TARGETS={'Office and facility consumables':40,'MRO tools and commercial hardware':30,'Packaging, shipping, storage and containers':15,'Basic IT accessories and standard equipment':10,'Mixed controls':5}
RESTRICT=['8(a)','hubzone','woman-owned','women-owned','wosb','edwosb','service-disabled','sdvosb','veteran-owned','vosb','buy indian','indian economic','local area']
MAND=['abilityone','skilcraft','national industries for the blind','unicor','federal prison industries','mandatory source']
VEHICLE_WORDS=['only holders of','existing idiq','existing bpa','bpa holders','schedule holders','task order competition','delivery order competition','fair opportunity notice']
TERM_KILLS={'Food / perishables':['food service','fresh fruit','fresh vegetable','meat products','milk products','produce delivery','catering','prepared meals'], 'Medical / pharmaceutical':['pharmaceutical','drug ','syringe','vaccine','patient care','surgical implant'], 'Fuel / petroleum':['aviation fuel','diesel fuel','gasoline','petroleum product'], 'Hazardous chemical':['hazmat','hazardous chemical','chemical disposal','pesticide','solvent','acid ','sealant','adhesive'], 'Construction / installation / repair / field service':['construction project','design-build','renovation','demolition','roofing','grounds maintenance','landscaping','janitorial service','repair service','installation service','maintenance service'], 'Rental / equipment-with-personnel':['equipment rental','daily shift','equipment & personnel','equipment and personnel','dispatch center','operator furnished','crew furnished'], 'Custom / personalized':['custom printing','personalized','embroidered','custom fabricated','made-to-order'], 'Broad/complex competition':['commercial solutions opening','broad agency announcement','white paper submission','multiple award contract','life cycle support activities','research announcement'], 'Large/specialized equipment':['padmount transformer','power transformer','transit bus program','light vehicles to include','sedans, light trucks','combat training center']}
OFFICE={'71','72','75','79'}; MRO={'34','41','43','44','47','48','49','51','52','53','61','62'}; PACK={'81'}
def sk(s):return re.sub(r'[^A-Z0-9]','',(s or '').upper())
def money(v):
 try:return float(re.sub(r'[^0-9.\-]','',v or ''))
 except:return None
def null(v):return (v or '').strip().lower() in {'','null','none','n/a'}
def track(psc):
 p=(psc or '').upper(); pref=p[:2]
 if pref in OFFICE:return 'Office and facility consumables'
 if pref in MRO:return 'MRO tools and commercial hardware'
 if pref in PACK:return 'Packaging, shipping, storage and containers'
 if p.startswith(('70','74')) or p.startswith('7'):return 'Basic IT accessories and standard equipment'
 return 'Mixed controls'
def setfit(s):
 low=(s or '').lower()
 if any(x in low for x in RESTRICT):return 'No — socioeconomic set-aside not held by GGG'
 if not low or 'no set' in low or 'total small business' in low or 'small business set-aside' in low:return 'Potentially yes — subject to historical SAM registration and representations'
 return 'Review — set-aside language requires validation'
def kill(r,text):
 p=(r.get('psc') or '').upper(); pref=p[:2]; sol=(r.get('solicitation_number') or '').upper(); sub=(r.get('subagency') or '').upper()
 if not p or not p[0].isdigit():return 'Service PSC / field-performance exposure'
 if pref in {'10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','28','29','69'}:return 'Vehicle, weapons, aircraft, training-system, or defense-platform product'
 for label,terms in TERM_KILLS.items():
  if any(t in text for t in terms):return label
 if any(x in text for x in ['nsn ','national stock number','approved source','source controlled','critical application item','flight safety']):return 'Restricted NSN / approved-source risk'
 if 'DEFENSE LOGISTICS AGENCY' in sub and re.match(r'^(SPE|SPR|SPM)',sol) and pref not in OFFICE|MRO|PACK|{'70','74'}:return 'DLA specialized product / NSN risk'
 return 'Pass / no automatic exclusion detected'
def repscore(r):
 d=r.get('description') or '';return min(len(d),2500)/100+(8 if r.get('additional_info') else 0)+(10 if not re.match(r'^amendment\b',d.strip(),re.I) else 0)+(2 if r.get('notice_type')=='Combined Synopsis/Solicitation' else 0)
with SOL.open(encoding='utf-8',newline='') as f:solrows=list(csv.DictReader(f))
with AWD.open(encoding='utf-8',newline='') as f:awards=list(csv.DictReader(f))
aw=defaultdict(list)
for a in awards:
 if sk(a.get('solicitation_number')):aw[sk(a.get('solicitation_number'))].append(a)
fams=defaultdict(list)
for r in solrows:fams[sk(r.get('solicitation_number')) or 'NOTICE'+r.get('notice_id','')].append(r)
cands=[]
for key,vs in fams.items():
 rep=max(vs,key=repscore);orig=min(vs,key=lambda x:x.get('posted_date_parsed','9999'));latest=max(vs,key=lambda x:x.get('posted_date_parsed',''));text=' '.join([rep.get('title',''),rep.get('description',''),orig.get('description','')]).lower();tr=track(rep.get('psc'));ex=kill(rep,text);sf=setfit(rep.get('set_aside'));mandatory='Probable mandatory-source conflict' if any(x in text for x in MAND) else 'No conflict detected in metadata; exact product review required';veh=any(x in text for x in VEHICLE_WORDS);openpath='No — vehicle-limited language detected' if veh else 'Potentially yes — original solicitation open to new offers';ggg='No — parent/limited vehicle path detected' if veh else sf
 detail=(2 if len(rep.get('description') or '')>=250 else 0)+(2 if re.search(r'\b(qty|quantity|each|case|pack|unit|clin|part number|model|salient|specification)\b',text) else 0)+(2 if rep.get('additional_info') else 0)+(1 if len(vs)>1 else 0);comp='Promising metadata; archive requirements review required' if detail>=4 else 'Partial metadata; archive retrieval required' if detail>=2 else 'Sparse metadata; high Gate 7 risk'
 outs=aw.get(key,[]);o=max(outs,key=lambda a:(0 if null(a.get('awardee')) else 2)+(1 if money(a.get('award_amount')) is not None else 0)+(1 if a.get('award_number') else 0),default=None);amt=money(o.get('award_amount')) if o else None;access=0 if veh or mandatory.startswith('Probable') or ggg.startswith('No') else 90 if ggg.startswith('Potentially') else 55;fit=0
 if ex.startswith('Pass'):
  fit=45+(15 if tr!='Mixed controls' else 0)+(15 if detail>=4 else 7 if detail>=2 else 0)+(15 if amt is not None and amt<=10000 else 8 if amt is not None and amt<=25000 else -15 if amt is not None and amt>50000 else 0)
 call='Strikeout' if access==0 or not ex.startswith('Pass') else 'Double' if comp.startswith('Sparse') else 'Grand Slam' if amt is not None and amt<=5000 and fit>=80 else 'Home Run' if fit>=75 else 'Triple' if fit>=65 else 'Double' if fit>=50 else 'Single';gate='Passes Gates 1-6 preliminarily; Gate 7 archive review pending'
 if veh:gate='Gate 3 — open competitive path'
 elif ggg.startswith('No'):gate='Gate 4 — GGG eligibility'
 elif mandatory.startswith('Probable'):gate='Gate 5 — mandatory source'
 elif not ex.startswith('Pass'):gate='Gate 6 — product/service exclusion'
 cands.append(dict(key=key,rep=rep,orig=orig,latest=latest,versions=vs,track=tr,ex=ex,sf=sf,mandatory=mandatory,openpath=openpath,ggg=ggg,detail=detail,comp=comp,o=o,amt=amt,access=access,fit=max(0,fit),call=call,gate=gate,period=rep.get('sample_period','')))
def rk(c):
 oq=2 if c['o'] and not null(c['o'].get('awardee')) and c['amt'] is not None else 1 if c['o'] else 0;amt=c['amt'] if c['amt'] is not None else 999999999;primary=0 if c['period'].startswith('Primary') else 1;h=int(hashlib.sha256(c['key'].encode()).hexdigest()[:12],16);return(primary,-c['detail'],-oq,amt,h)
preferred=[c for c in cands if c['track']!='Mixed controls' and c['access']>0 and c['ex'].startswith('Pass')]
selected=[];keys=set();short={}
for tr,q in TARGETS.items():
 if tr=='Mixed controls':continue
 pool=sorted([c for c in preferred if c['track']==tr],key=rk);take=pool[:q];selected+=take;keys.update(c['key'] for c in take);short[tr]=max(0,q-len(take))
for c in sorted([x for x in preferred if x['key'] not in keys],key=rk):
 if len(selected)>=80:break
 selected.append(c);keys.add(c['key'])
rest=[c for c in cands if c['key'] not in keys];controls=[]
controls+=sorted([c for c in rest if c['access']>0 and c['ex'].startswith('Pass')],key=lambda c:(abs(c['fit']-40),rk(c)))[:5]
controls+=sorted([c for c in rest if c['gate'].startswith('Gate 4') and c not in controls],key=rk)[:5]
controls+=sorted([c for c in rest if c['gate'].startswith('Gate 5') and c not in controls],key=rk)[:5]
controls+=sorted([c for c in rest if c['gate'].startswith('Gate 6') and c not in controls],key=rk)[:15]
selected+=controls;keys.update(c['key'] for c in controls)
for c in sorted([x for x in cands if x['key'] not in keys],key=rk):
 if len(selected)>=100:break
 selected.append(c);keys.add(c['key'])
selected=selected[:100];assert len(selected)==100
rows=[];gates=Counter();tracks=Counter();ag=Counter();calls=Counter();periods=Counter();mapped=0
for i,c in enumerate(selected,1):
 r=c['rep'];o=c['o'];gates[c['gate']]+=1;tracks[c['track']]+=1;ag[r.get('agency') or 'Unknown']+=1;calls[c['call']]+=1;periods[c['period']]+=1;mapped+=bool(o);pop=', '.join(x for x in [r.get('city'),r.get('state'),r.get('zip'),r.get('country')] if x);vids='; '.join(v.get('notice_id','') for v in sorted(c['versions'],key=lambda x:x.get('posted_date_parsed','')))
 rows.append({'Intake ID':f'HOS01-{i:03d}','Notice ID':r.get('notice_id',''),'Solicitation Number':r.get('solicitation_number',''),'Historical Source URL':r.get('historical_source_url',''),'Notice Type':r.get('notice_type',''),'Posted Date':c['orig'].get('posted_date_parsed',''),'Original Response Deadline':c['latest'].get('response_deadline_parsed') or r.get('response_deadline_parsed',''),'Agency':r.get('agency',''),'Subagency':r.get('subagency',''),'Contracting Office':r.get('contracting_office',''),'Title':r.get('title',''),'Description':(r.get('description') or '')[:1800],'NAICS':r.get('naics',''),'PSC':r.get('psc',''),'Set-Aside Type':r.get('set_aside',''),'Estimated Value':'Unknown pre-award; historical award retained only as answer key when mapped','Product or Service':'Commercial product candidate' if c['ex'].startswith('Pass') else 'Excluded/control category','Supply Track':c['track'],'Place of Performance':pop,'Delivery Destination':pop or 'Archive review required','Attachments Available':'Archive retrieval required; AdditionalInfoLink present' if r.get('additional_info') else 'Direct notice/resource lookup required','Amendments Available':f"Yes — {len(c['versions'])} notice version(s)" if len(c['versions'])>1 else 'No separate version identified in extract','Q&A Available':'Unknown — archive retrieval required','Award Outcome Available':'Mapped from award index' if o else 'Not yet recovered','Award Notice URL':o.get('historical_source_url','') if o else '','Awardee':'' if not o or null(o.get('awardee')) else o.get('awardee',''),'Award Amount':'' if not o else o.get('award_amount',''),'Award Type':o.get('notice_type','') if o else '','Parent Award ID':'No parent vehicle indicated at solicitation intake; verify clauses','Open Competitive Path':c['openpath'],'Parent Vehicle Required':'No evidence in metadata; verify solicitation' if c['openpath'].startswith('Potentially') else 'Yes / probable','Could GGG Compete At Time':c['ggg'],'Mandatory-Source Status':c['mandatory'],'AbilityOne Status':'Exact product/NSN review required','Product-Exclusion Result':c['ex'],'Requirement Completeness':c['comp'],'Payment-Method Evidence':'Unknown — never infer from award amount','Preliminary Supplier Exposure':'Not modeled before archive and supplier-pricing gates','Exposure Classification':'Unclassified pending requirements and sourcing','Preliminary Probable Net':'Not modeled before supplier pricing','Preliminary Accessibility Score':c['access'],'Preliminary Kickoff Fit Score':c['fit'],'Preliminary Baseball Call':c['call'],'Primary Failure Point':c['gate'],'Intake Decision':'REVIEW — archive reconstruction' if c['gate'].startswith('Passes') else 'NO-BID / CONTROL','Confidence':'Moderate — official extract metadata; direct archive review pending','Notes':f"Sample period: {c['period']}. Strict PSC-family lane classification. Solicitation family has {len(c['versions'])} version(s): {vids}. Outcome did not control selection.",'Source Extract Row':r.get('source_extract_row','')})
headers=list(rows[0]);
with (OUT/'sam_balanced_intake_100.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
summary={'sample_method':'Strict product-PSC family classification; 2023-2024 prioritized; 2022 used only for shortages; service PSC, vehicle, training-system, broad-MAC and large specialized equipment false positives excluded.','solicitation_universe_rows':len(solrows),'distinct_solicitation_families':len(cands),'selected':100,'target_quotas':TARGETS,'quota_shortage_before_fill':short,'sample_period_use':dict(periods),'gate_counts':dict(gates),'supply_tracks':dict(tracks),'top_agencies':ag.most_common(15),'baseball_calls':dict(calls),'mapped_outcomes':mapped,'archive_review_count':sum(r['Intake Decision'].startswith('REVIEW') for r in rows),'control_or_reject_count':sum(not r['Intake Decision'].startswith('REVIEW') for r in rows),'sampling_corrections':['Outcome-conditioned sample rejected.','Service-PSC false positives rejected.','Substring lane-classification bug removed.','Preferred lanes now require strict PSC-family evidence.']}
(OUT/'sam_balanced_intake_100_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
