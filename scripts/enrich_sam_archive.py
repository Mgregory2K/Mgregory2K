#!/usr/bin/env python3
import csv, json, time, re
from pathlib import Path
from urllib.parse import urlencode
import requests

OUT=Path('data/green_gregory')
SRC=OUT/'sam_balanced_intake_100.csv'
DEST=OUT/'archive_enrichment'
DEST.mkdir(parents=True,exist_ok=True)
UA={'User-Agent':'Mozilla/5.0 (compatible; GreenGregoryHistoricalResearch/1.0)'}
SEARCH='https://sam.gov/api/prod/sgs/v1/search/'
DESC='https://api.sam.gov/opportunities/v1/noticedesc'

with SRC.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))

def norm(s): return re.sub(r'[^a-z0-9]','',(s or '').lower())
def results_from(data):
    if isinstance(data,list): return data
    if not isinstance(data,dict): return []
    for path in [('opportunitiesData',),('_embedded','results'),('results',),('data','results'),('content',)]:
        cur=data
        ok=True
        for p in path:
            if not isinstance(cur,dict) or p not in cur: ok=False; break
            cur=cur[p]
        if ok and isinstance(cur,list): return cur
    return []

def extract_files(data,notice_id):
    files=[]
    if not isinstance(data,dict): return files
    attachments=data.get('attachments') or (data.get('data') or {}).get('attachments') or []
    for att in attachments if isinstance(attachments,list) else []:
        if not isinstance(att,dict): continue
        fi=att.get('fileInformation') or att.get('fileInfomation') or {}
        fid=fi.get('fileID') or fi.get('fileId') or ''
        name=fi.get('fileName') or att.get('name') or att.get('filename') or 'attachment'
        url=f'https://sam.gov/api/prod/opps/v3/opportunities/{notice_id}/resources/files/{fid}/download?api_key=DEMO_KEY' if fid else att.get('url','')
        files.append({'file_id':fid,'filename':name,'url':url})
    for result in results_from(data)[:1]:
        for link in result.get('resourceLinks') or []:
            if link and not any(x.get('url')==link for x in files): files.append({'file_id':'','filename':link.rsplit('/',1)[-1] or 'attachment','url':link})
    return files

def pick_exact(results,notice,sol):
    for x in results:
        xid=str(x.get('noticeId') or x.get('noticeID') or x.get('_id') or '')
        if xid==notice:return x
    ns=norm(sol)
    for x in results:
        xs=norm(str(x.get('solicitationNumber') or x.get('solNum') or x.get('solicitation') or ''))
        if ns and xs==ns:return x
    return results[0] if results else None

enriched=[]; counts={'total':len(rows),'search_success':0,'noticedesc_success':0,'attachment_manifest_recovered':0,'description_recovered':0,'gate7_likely_pass':0,'gate7_review':0,'gate7_fail':0}
for idx,r in enumerate(rows,1):
    notice=r['Notice ID']; sol=r['Solicitation Number']
    rec={'intake_id':r['Intake ID'],'notice_id':notice,'solicitation_number':sol,'search_status':'','noticedesc_status':'','search_result':None,'noticedesc':None,'attachments':[],'recovered_description':'','retrieval_errors':[]}
    # Internal browser search endpoint first; this does not require the user's SAM API key.
    try:
        params={'index':'opp','page':'0','sort':'-modifiedDate','size':'25','mode':'search','responseType':'json','qMode':'ALL','is_active':'false','q':notice or sol}
        resp=requests.get(SEARCH,params=params,headers=UA,timeout=40)
        rec['search_status']=str(resp.status_code)
        if resp.status_code==200:
            data=resp.json(); exact=pick_exact(results_from(data),notice,sol)
            if exact:
                rec['search_result']=exact; counts['search_success']+=1
                rec['recovered_description']=str(exact.get('description') or exact.get('descriptionText') or '')
                rec['attachments'].extend(extract_files(exact,notice))
    except Exception as e: rec['retrieval_errors'].append('search:'+repr(e))
    # Public noticedesc fallback using GSA's DEMO_KEY, never a user secret.
    try:
        resp=requests.get(DESC,params={'noticeid':notice,'api_key':'DEMO_KEY'},headers=UA,timeout=40)
        rec['noticedesc_status']=str(resp.status_code)
        if resp.status_code==200:
            data=resp.json(); rec['noticedesc']=data; counts['noticedesc_success']+=1
            if not rec['recovered_description']:
                rec['recovered_description']=str(data.get('description') or (data.get('data') or {}).get('description') or '')
            for x in extract_files(data,notice):
                if not any(y.get('url')==x.get('url') for y in rec['attachments']): rec['attachments'].append(x)
    except Exception as e: rec['retrieval_errors'].append('noticedesc:'+repr(e))
    if rec['attachments']: counts['attachment_manifest_recovered']+=1
    if rec['recovered_description']: counts['description_recovered']+=1
    combined=(r.get('Description','')+' '+rec['recovered_description']).lower()
    complete_signals=sum(bool(re.search(p,combined)) for p in [r'\b(qty|quantity|each|case|pack|unit|units|clin)\b',r'\b(part number|model|brand name|salient characteristics|specification|nsn)\b',r'\b(delivery|ship to|fob|destination)\b',r'\b(quote|proposal|submission|email)\b'])
    if rec['attachments'] and complete_signals>=2:
        gate7='Likely pass — attachment manifest and key requirement signals recovered'; counts['gate7_likely_pass']+=1
    elif rec['attachments'] or len(rec['recovered_description'])>=300 or complete_signals>=2:
        gate7='Review — partial archive evidence recovered'; counts['gate7_review']+=1
    else:
        gate7='Fail / replace — insufficient recoverable requirement evidence'; counts['gate7_fail']+=1
    rec['gate7_archive_result']=gate7
    compact={k:v for k,v in rec.items() if k!='noticedesc'}
    (DEST/f"{r['Intake ID']}_{notice}.json").write_text(json.dumps(compact,indent=2)[:500000],encoding='utf-8')
    enriched.append({'Intake ID':r['Intake ID'],'Notice ID':notice,'Solicitation Number':sol,'Search Status':rec['search_status'],'NoticeDesc Status':rec['noticedesc_status'],'Description Recovered':'Yes' if rec['recovered_description'] else 'No','Attachment Count':len(rec['attachments']),'Attachment Names':'; '.join(x.get('filename','') for x in rec['attachments']),'Gate 7 Archive Result':gate7,'Archive JSON':f"archive_enrichment/{r['Intake ID']}_{notice}.json",'Errors':' | '.join(rec['retrieval_errors'])})
    time.sleep(.15)

with (OUT/'sam_archive_enriched_100.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(enriched[0])); w.writeheader(); w.writerows(enriched)
for k in range(10):
    (OUT/f'sam_archive_enriched_part{k+1:02d}.json').write_text(json.dumps(enriched[k*10:(k+1)*10],indent=2),encoding='utf-8')
(OUT/'sam_archive_enrichment_summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
print(json.dumps(counts,indent=2))
