#!/usr/bin/env python3
import csv,json,re,hashlib
from collections import Counter,defaultdict
from pathlib import Path
OUT=Path('data/green_gregory'); SOL=OUT/'sam_historical_open_2022_2024.csv'; AWD=OUT/'sam_award_notice_index_2022_2025.csv'
TARGETS={'Office and facility consumables':40,'MRO tools and commercial hardware':30,'Packaging, shipping, storage and containers':15,'Basic IT accessories and standard equipment':10,'Mixed controls':5}
RESTRICT=['8(a)','8a ','hubzone','woman-owned','women-owned','wosb','edwosb','service-disabled','sdvosb','veteran-owned','vosb','buy indian','indian economic','local area']
MAND=['abilityone','skilcraft','national industries for the blind','unicor','federal prison industries','mandatory source']
VEH=['only holders of','existing idiq','existing bpa','bpa holders','schedule holders','task order competition','delivery order competition','fair opportunity notice']
AUTOKILL={'Food / perishables':['food service','fresh fruit','fresh vegetable','meat','milk','produce','catering','meals'], 'Medical / pharmaceutical':['pharmaceutical','drug ','syringe','vaccine','patient care','surgical','implant'], 'Fuel / petroleum':['aviation fuel','diesel fuel','gasoline','petroleum'], 'Hazardous chemical':['hazmat','hazardous chemical','chemical disposal','pesticide','solvent','acid ','sealant','adhesive'], 'Construction / installation / repair / field service':['construction','renovation','demolition','roofing','grounds maintenance','landscaping','janitorial service','repair service','installation service','maintenance service'], 'Rental / equipment-with-personnel':['rental','daily shift','equipment & personnel','equipment and personnel','dispatch center','operator furnished','crew furnished'], 'Custom / personalized':['custom printing','personalized','embroidered','custom fabricated','made-to-order'], 'Safety-critical / defense platform':['aircraft part','airframe','weapon system','missile','flight critical','nuclear','armored vehicle'], 'Broad/non-product competition':['commercial solutions opening','broad agency announcement','white paper submission','research announcement']}
WORDS={'Office and facility consumables':['copy paper','xerographic','toner','ink cartridge','envelope','binder','file folder','notebook','pen ','pencil','trash bag','paper towel','toilet tissue','facial tissue','light bulb','led lamp','battery','batteries','tableware','office chair','desk','shredder','janitorial supplies'], 'MRO tools and commercial hardware':['hand tool','power tool','wrench','socket set','screwdriver','drill','saw blade','bolt cutter','fastener','commercial hardware','ladder','hose','valve','bearing','filter','pump','abrasive','sandpaper','grinding wheel','work light','headlamp','toolbox','extension cord'], 'Packaging, shipping, storage and containers':['packaging','shipping box','carton','container','pallet','crate','storage bin','plastic bag','poly bag','stretch wrap','strapping','packing tape','bubble wrap'], 'Basic IT accessories and standard equipment':['computer monitor','keyboard','mouse','printer','scanner','network switch','router','ethernet','network cable','usb cable','headset','ups ','laptop','tablet','webcam','docking station','hard drive','ssd','memory module','projector']}

def n(s):return re.sub(r'[^a-z0-9]','',(s or '').lower())
def solkey(s):return re.sub(r'[^A-Z0-9]','',(s or '').upper())
def money(v):
 try:return float(re.sub(r'[^0-9.\-]','',v or ''))
 except:return None
def null(v):return (v or '').strip().lower() in {'','null','none','n/a'}
def product_psc(p):return bool(p) and p[0].isdigit()
def setfit(s):
 low=(s or '').lower()
 if any(x in low for x in RESTRICT):return 'No — socioeconomic set-aside not held by GGG'
 if not low or 'no set' in low or 'total small business' in low or 'small business set-aside' in low:return 'Potentially yes — subject to historical SAM registration and representations'
 return 'Review — set-aside language requires validation'
def kill(row,text):
 p=(row.get('psc') or '').upper(); sol=(row.get('solicitation_number') or '').upper(); sub=(row.get('subagency') or '').upper()
 if p and not product_psc(p):return 'Service PSC / field-performance exposure'
 for label,terms in AUTOKILL.items():
  if any(t in text for t in terms):return label
 if any(x in text for x in ['nsn ','national stock number','approved source','source controlled','critical application item','flight safety']):return 'Restricted NSN / approved-source risk'
 if 'DEFENSE LOGISTICS AGENCY' in sub and re.match(r'^(SPE|SPR|SPM)',sol) and p[:2] in {'10','11','12','13','14','15','16','17','18','19','20','22','23','25','26','28','29','30','31','32','35','36','37','38','39','40','42','58','59','61','62','66'}:return 'Defense-platform / restricted NSN risk'
 return 'Pass / no automatic exclusion detected'
def track(row,text):
 p=(row.get('psc') or '').upper(); na=row.get('naics') or ''
 if not product_psc(p):return 'Mixed controls'
 scores={k:sum(x in text for x in v) for k,v in WORDS.items()}
 if p.startswith(('71','72','75','79')):scores['Office and facility consumables']+=5
 if p.startswith(('34','41','43','44','47','48','49','51','52','53')):scores['MRO tools and commercial hardware']+=5
 if p.startswith('81'):scores['Packaging, shipping, storage and containers']+=6
 if p.startswith(('70','74')) or p.startswith('7') or na in {'334111','334112','334118','423430'}:scores['Basic IT accessories and standard equipment']+=5
 b=max(scores,key=scores.get);return b if scores[b]>0 else 'Mixed controls'
def rep_score(r):
 d=r.get('description') or ''; s=min(len(d),2500)/100
 if r.get('additional_info'):s+=8
 if not re.match(r'^amendment\b',d.strip(),re.I):s+=10
 if r.get('notice_type')=='Combined Synopsis/Solicitation':s+=2
 return s
with SOL.open(encoding='utf-8',newline='') as f:solrows=list(csv.DictReader(f))
with AWD.open(encoding='utf-8',newline='') as f:awards=list(csv.DictReader(f))
aw=defaultdict(list)
for a in awards:
 k=solkey(a.get('solicitation_number'))
 if k:aw[k].append(a)
fams=defaultdict(list)
for r in solrows:fams[solkey(r.get('solicitation_number')) or 'NOTICE'+(r.get('notice_id') or '')].append(r)
cands=[]
for k,vs in fams.items():
 rep=max(vs,key=rep_score); orig=min(vs,key=lambda x:x.get('posted_date_parsed','9999')); latest=max(vs,key=lambda x:x.get('posted_date_parsed',''))
 text=' '.join([rep.get('title',''),rep.get('description',''),orig.get('description','')]).lower(); tr=track(rep,text); ex=kill(rep,text); sf=setfit(rep.get('set_aside')); mandatory='Probable mandatory-source conflict' if any(x in text for x in MAND) else 'No conflict detected in metadata; exact product review required'; veh=any(x in text for x in VEH)
 openpath='No — vehicle-limited language detected' if veh else 'Potentially yes — original solicitation open to new offers'; ggg='No — parent/limited vehicle path detected' if veh else sf
 detail=(2 if len(rep.get('description') or '')>=250 else 0)+(2 if re.search(r'\b(qty|quantity|each|case|pack|unit|clin|part number|model|salient|specification)\b',text) else 0)+(2 if rep.get('additional_info') else 0)+(1 if len(vs)>1 else 0)
 comp='Promising metadata; archive requirements review required' if detail>=4 else 'Partial metadata; archive retrieval required' if detail>=2 else 'Sparse metadata; high Gate 7 risk'
 outs=aw.get(k,[]); outcome=max(outs,key=lambda a:(0 if null(a.get('awardee')) else 2)+(1 if money(a.get('award_amount')) is not None else 0)+(1 if a.get('award_number') else 0),default=None); amount=money(outcome.get('award_amount')) if outcome else None
 access=0 if veh or mandatory.startswith('Probable') or ggg.startswith('No') else 90 if ggg.startswith('Potentially') else 55
 fit=0
 if ex.startswith('Pass'):
  fit=45+(15 if tr!='Mixed controls' else 0)+(15 if detail>=4 else 7 if detail>=2 else 0)+(15 if amount is not None and amount<=10000 else 8 if amount is not None and amount<=25000 else -15 if amount is not None and amount>50000 else 0)
 if access==0 or not ex.startswith('Pass'):call='Strikeout'
 elif comp.startswith('Sparse'):call='Double'
 elif amount is not None and amount<=5000 and fit>=80:call='Grand Slam'
 elif fit>=75:call='Home Run'
 elif fit>=65:call='Triple'
 elif fit>=50:call='Double'
 else:call='Single'
 gate='Passes Gates 1-6 preliminarily; Gate 7 archive review pending'
 if veh:gate='Gate 3 — open competitive path'
 elif ggg.startswith('No'):gate='Gate 4 — GGG eligibility'
 elif mandatory.startswith('Probable'):gate='Gate 5 — mandatory source'
 elif not ex.startswith('Pass'):gate='Gate 6 — product/service exclusion'
 cands.append(dict(key=k,rep=rep,orig=orig,latest=latest,versions=vs,text=text,track=tr,exclusion=ex,setfit=sf,mandatory=mandatory,openpath=openpath,ggg=ggg,comp=comp,detail=detail,outcome=outcome,amount=amount,access=access,fit=max(0,fit),call=call,gate=gate,period=rep.get('sample_period','')))

def rk(c):
 oq=2 if c['outcome'] and not null(c['outcome'].get('awardee')) and c['amount'] is not None else 1 if c['outcome'] else 0; amt=c['amount'] if c['amount'] is not None else 999999999; primary=0 if c['period'].startswith('Primary') else 1; h=int(hashlib.sha256(c['key'].encode()).hexdigest()[:12],16);return(primary,-c['detail'],-oq,amt,h)
preferred=[c for c in cands if c['track']!='Mixed controls' and c['access']>0 and c['exclusion'].startswith('Pass')]
selected=[];keys=set();short={};period_use=Counter()
for tr,q in TARGETS.items():
 if tr=='Mixed controls':continue
 pool=sorted([c for c in preferred if c['track']==tr],key=rk); take=pool[:q]; selected+=take;keys.update(c['key'] for c in take);short[tr]=max(0,q-len(take))
for c in sorted([x for x in preferred if x['key'] not in keys],key=rk):
 if len(selected)>=95:break
 selected.append(c);keys.add(c['key'])
controls=[];rest=[c for c in cands if c['key'] not in keys]
controls += sorted([c for c in rest if c['access']>0 and c['exclusion'].startswith('Pass')],key=lambda c:(abs(c['fit']-40),rk(c)))[:2]
controls += sorted([c for c in rest if c['gate'].startswith('Gate 4') and c not in controls],key=rk)[:1]
controls += sorted([c for c in rest if c['gate'].startswith('Gate 6') and c not in controls],key=rk)[:2]
selected+=controls;keys.update(c['key'] for c in controls)
for c in sorted([x for x in cands if x['key'] not in keys],key=rk):
 if len(selected)>=100:break
 selected.append(c);keys.add(c['key'])
selected=selected[:100];assert len(selected)==100
rows=[];gates=Counter();tracks=Counter();agencies=Counter();calls=Counter();mapped=0
for i,c in enumerate(selected,1):
 r=c['rep'];o=c['outcome'];gates[c['gate']]+=1;tracks[c['track']]+=1;agencies[r.get('agency') or 'Unknown']+=1;calls[c['call']]+=1;period_use[c['period']]+=1;mapped+=bool(o)
 pop=', '.join(x for x in [r.get('city'),r.get('state'),r.get('zip'),r.get('country')] if x);vids='; '.join(v.get('notice_id','') for v in sorted(c['versions'],key=lambda x:x.get('posted_date_parsed','')));ou=o.get('historical_source_url','') if o else '';awardee='' if not o or null(o.get('awardee')) else o.get('awardee','');awardamt='' if not o else o.get('award_amount','')
 rows.append({'Intake ID':f'HOS01-{i:03d}','Notice ID':r.get('notice_id',''),'Solicitation Number':r.get('solicitation_number',''),'Historical Source URL':r.get('historical_source_url',''),'Notice Type':r.get('notice_type',''),'Posted Date':c['orig'].get('posted_date_parsed',''),'Original Response Deadline':c['latest'].get('response_deadline_parsed') or r.get('response_deadline_parsed',''),'Agency':r.get('agency',''),'Subagency':r.get('subagency',''),'Contracting Office':r.get('contracting_office',''),'Title':r.get('title',''),'Description':(r.get('description') or '')[:1800],'NAICS':r.get('naics',''),'PSC':r.get('psc',''),'Set-Aside Type':r.get('set_aside',''),'Estimated Value':'Unknown pre-award; historical award retained only as answer key when mapped','Product or Service':'Commercial product candidate' if c['exclusion'].startswith('Pass') else 'Excluded/control category','Supply Track':c['track'],'Place of Performance':pop,'Delivery Destination':pop or 'Archive review required','Attachments Available':'Archive retrieval required; AdditionalInfoLink present' if r.get('additional_info') else 'Direct notice/resource lookup required','Amendments Available':f"Yes — {len(c['versions'])} notice version(s)" if len(c['versions'])>1 else 'No separate version identified in extract','Q&A Available':'Unknown — archive retrieval required','Award Outcome Available':'Mapped from award index' if o else 'Not yet recovered','Award Notice URL':ou,'Awardee':awardee,'Award Amount':awardamt,'Award Type':o.get('notice_type','') if o else '','Parent Award ID':'No parent vehicle indicated at solicitation intake; verify clauses','Open Competitive Path':c['openpath'],'Parent Vehicle Required':'No evidence in metadata; verify solicitation' if c['openpath'].startswith('Potentially') else 'Yes / probable','Could GGG Compete At Time':c['ggg'],'Mandatory-Source Status':c['mandatory'],'AbilityOne Status':'Exact product/NSN review required','Product-Exclusion Result':c['exclusion'],'Requirement Completeness':c['comp'],'Payment-Method Evidence':'Unknown — never infer from award amount','Preliminary Supplier Exposure':'Not modeled before archive and supplier-pricing gates','Exposure Classification':'Unclassified pending requirements and sourcing','Preliminary Probable Net':'Not modeled before supplier pricing','Preliminary Accessibility Score':c['access'],'Preliminary Kickoff Fit Score':c['fit'],'Preliminary Baseball Call':c['call'],'Primary Failure Point':c['gate'],'Intake Decision':'REVIEW — archive reconstruction' if c['gate'].startswith('Passes') else 'NO-BID / CONTROL','Confidence':'Moderate — official extract metadata; direct archive review pending','Notes':f"Sample period: {c['period']}. Solicitation family has {len(c['versions'])} version(s): {vids}. Representative selected by product-PSC, lane fit and detail; outcome did not control selection.",'Source Extract Row':r.get('source_extract_row','')})
headers=list(rows[0]);
with (OUT/'sam_balanced_intake_100.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
for k in range(4):(OUT/f'sam_balanced_intake_100_part{k+1}.json').write_text(json.dumps(rows[k*25:(k+1)*25],indent=2),encoding='utf-8')
summary={'sample_method':'Distinct solicitation families; product PSC required for preferred supply lanes; 2023-2024 prioritized and 2022 used only for shortages; selection independent of outcomes.','solicitation_universe_rows':len(solrows),'distinct_solicitation_families':len(cands),'selected':100,'target_quotas':TARGETS,'quota_shortage_before_fill':short,'sample_period_use':dict(period_use),'gate_counts':dict(gates),'supply_tracks':dict(tracks),'top_agencies':agencies.most_common(15),'baseball_calls':dict(calls),'mapped_outcomes':mapped,'archive_review_count':sum(r['Intake Decision'].startswith('REVIEW') for r in rows),'control_or_reject_count':sum(not r['Intake Decision'].startswith('REVIEW') for r in rows),'sampling_corrections':['Rejected outcome-conditioned pass: 98/100 rejects, 88/100 DoD, amendment duplication.','Rejected service-PSC false positives: firefighting/equipment-with-personnel and broad CSO records were incorrectly labeled supplies.','Preferred lanes now require numeric product PSC evidence.']}
(OUT/'sam_balanced_intake_100_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
