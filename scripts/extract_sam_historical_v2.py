#!/usr/bin/env python3
import csv,json,re,urllib.request
from collections import Counter
from datetime import datetime,date
from pathlib import Path
URL='https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv'
OUT=Path('data/green_gregory'); OUT.mkdir(parents=True,exist_ok=True); RAW=OUT/'ContractOpportunitiesFullCSV.csv'
def norm(s):return re.sub(r'[^a-z0-9]','',(s or '').lower())
def dt(v):
 v=(v or '').strip().replace('Z','')
 for c in [v,v[:10],v.split('T')[0],v.split(' ')[0]]:
  for f in ['%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%Y/%m/%d','%Y-%m-%d %H:%M:%S']:
   try:return datetime.strptime(c,f).date()
   except:pass
 return None
urllib.request.urlretrieve(URL,RAW)
with RAW.open(encoding='utf-8-sig',errors='replace',newline='') as f:
 reader=csv.DictReader(f); fields=reader.fieldnames or []; km={norm(x):x for x in fields}
 aliases={'notice_id':['noticeid'],'title':['title'],'solicitation_number':['sol'],'agency':['departmentindagency'],'subagency':['subtier'],'contracting_office':['office'],'posted_date':['posteddate'],'notice_type':['type'],'base_type':['basetype'],'archive_type':['archivetype'],'archive_date':['archivedate'],'set_aside':['setaside'],'set_aside_code':['setasidecode'],'response_deadline':['responsedeadline'],'naics':['naicscode'],'psc':['classificationcode'],'active':['active'],'description':['description'],'additional_info':['additionalinfolink'],'record_link':['link'],'award_number':['awardnumber'],'award_amount':['award'],'awardee':['awardee'],'award_date':['awarddate'],'city':['popcity'],'state':['popstate'],'zip':['popzip'],'country':['popcountry']}
 res={k:next((km[o] for o in opts if o in km),None) for k,opts in aliases.items()}; sol=[]; awards=[]; counts=Counter(); allowed={'solicitation','combinedsynopsissolicitation'}
 for source_row,row in enumerate(reader,2):
  counts['total_rows']+=1
  def g(k):return (row.get(res[k],'') if res.get(k) else '').strip()
  pd=dt(g('posted_date')); typ=norm(g('notice_type'))
  if pd and date(2022,1,1)<=pd<=date(2025,12,31) and (typ=='awardnotice' or g('award_number') or g('awardee') or g('award_amount')):
   c={k:g(k) for k in aliases}; c.update(source_extract_row=source_row,posted_date_parsed=pd.isoformat(),award_date_parsed=(dt(g('award_date')).isoformat() if dt(g('award_date')) else ''),historical_source_url=g('record_link') or (f"https://sam.gov/opp/{g('notice_id')}/view" if g('notice_id') else '')); awards.append(c); counts['award_index_rows']+=1
  if not pd or not(date(2022,1,1)<=pd<=date(2024,12,31)):continue
  if typ not in allowed:continue
  rd=dt(g('response_deadline'))
  if not rd or rd>date(2024,12,31):continue
  c={k:g(k) for k in aliases}; ad=dt(g('archive_date')); c.update(source_extract_row=source_row,historical_source_url=g('record_link') or (f"https://sam.gov/opp/{g('notice_id')}/view" if g('notice_id') else ''),posted_date_parsed=pd.isoformat(),response_deadline_parsed=rd.isoformat(),archive_date_parsed=(ad.isoformat() if ad else ''),sample_period=('Primary 2023-2024' if pd>=date(2023,1,1) else '2022 fallback'),historical_status_basis='Deadline passed by 2024-12-31; direct archive verification required.'); sol.append(c); counts['solicitation_rows']+=1; counts['primary_2023_2024' if pd>=date(2023,1,1) else 'fallback_2022']+=1
cols=list(aliases)+['source_extract_row','historical_source_url','posted_date_parsed','response_deadline_parsed','archive_date_parsed','sample_period','historical_status_basis']
with (OUT/'sam_historical_open_2022_2024.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(sol)
acols=list(aliases)+['source_extract_row','posted_date_parsed','award_date_parsed','historical_source_url']
with (OUT/'sam_award_notice_index_2022_2025.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=acols);w.writeheader();w.writerows(awards)
(OUT/'sam_extract_profile_v2.json').write_text(json.dumps({'source_url':URL,'retrieved_utc':datetime.utcnow().isoformat()+'Z','counts':dict(counts),'resolved_columns':res,'method':'2023-2024 primary; 2022 retained only as fallback for supply-lane shortages.'},indent=2),encoding='utf-8')
print(json.dumps(dict(counts),indent=2))
