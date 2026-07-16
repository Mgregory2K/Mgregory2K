#!/usr/bin/env python3
import csv, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
import requests

OUT=Path('data/green_gregory'); SRC=OUT/'sam_balanced_intake_100.csv'; DEST=OUT/'archive_enrichment_fast'; DEST.mkdir(parents=True,exist_ok=True)
SEARCH='https://sam.gov/api/prod/sgs/v1/search/'; DESC='https://api.sam.gov/opportunities/v1/noticedesc'; UA={'User-Agent':'Mozilla/5.0 (compatible; GreenGregoryHistoricalResearch/1.0)'}
with SRC.open(encoding='utf-8',newline='') as f: all_rows=list(csv.DictReader(f))
rows=[r for r in all_rows if (r.get('Intake Decision') or '').startswith('REVIEW')]

def results(data):
    if isinstance(data,list):return data
    if not isinstance(data,dict):return []
    for path in [('opportunitiesData',),('_embedded','results'),('results',),('data','results'),('content',)]:
        cur=data
        for p in path:
            if not isinstance(cur,dict) or p not in cur:cur=None;break
            cur=cur[p]
        if isinstance(cur,list):return cur
    return []

def files(data,notice):
    out=[]
    if not isinstance(data,dict):return out
    atts=data.get('attachments') or (data.get('data') or {}).get('attachments') or []
    for a in atts if isinstance(atts,list) else []:
        if not isinstance(a,dict):continue
        fi=a.get('fileInformation') or a.get('fileInfomation') or {}; fid=fi.get('fileID') or fi.get('fileId') or ''; name=fi.get('fileName') or a.get('name') or a.get('filename') or 'attachment'
        out.append({'file_id':fid,'filename':name,'url':f'https://sam.gov/api/prod/opps/v3/opportunities/{notice}/resources/files/{fid}/download?api_key=DEMO_KEY' if fid else a.get('url','')})
    return out

def exact(rs,notice,sol):
    ns=re.sub(r'[^A-Z0-9]','',(sol or '').upper())
    for x in rs:
        if str(x.get('noticeId') or x.get('noticeID') or x.get('_id') or '')==notice:return x
    for x in rs:
        xs=re.sub(r'[^A-Z0-9]','',str(x.get('solicitationNumber') or x.get('solNum') or x.get('solicitation') or '').upper())
        if ns and xs==ns:return x
    return rs[0] if rs else None

def one(r):
    notice=r['Notice ID']; sol=r['Solicitation Number']; rec={'Intake ID':r['Intake ID'],'Notice ID':notice,'Solicitation Number':sol,'Search Status':'','NoticeDesc Status':'','Description Recovered':'No','Attachment Count':0,'Attachment Names':'','Gate 7 Archive Result':'','Archive JSON':'','Errors':''}; raw={'search':None,'noticedesc':None,'attachments':[]}; errs=[]; desc=''
    try:
        p={'index':'opp','page':'0','sort':'-modifiedDate','size':'25','mode':'search','responseType':'json','qMode':'ALL','is_active':'false','q':notice or sol}
        q=requests.get(SEARCH,params=p,headers=UA,timeout=(4,8));rec['Search Status']=str(q.status_code)
        if q.status_code==200:
            x=exact(results(q.json()),notice,sol);raw['search']=x
            if x:desc=str(x.get('description') or x.get('descriptionText') or '');raw['attachments']+=files(x,notice)
    except Exception as e:errs.append('search:'+type(e).__name__)
    try:
        q=requests.get(DESC,params={'noticeid':notice,'api_key':'DEMO_KEY'},headers=UA,timeout=(4,8));rec['NoticeDesc Status']=str(q.status_code)
        if q.status_code==200:
            x=q.json();raw['noticedesc']=x
            if not desc:desc=str(x.get('description') or (x.get('data') or {}).get('description') or '')
            for a in files(x,notice):
                if not any(z.get('url')==a.get('url') for z in raw['attachments']):raw['attachments'].append(a)
    except Exception as e:errs.append('noticedesc:'+type(e).__name__)
    combined=(r.get('Description','')+' '+desc).lower();signals=sum(bool(re.search(p,combined)) for p in [r'\b(qty|quantity|each|case|pack|unit|units|clin)\b',r'\b(part number|model|brand name|salient characteristics|specification|nsn)\b',r'\b(delivery|ship to|fob|destination)\b',r'\b(quote|proposal|submission|email)\b'])
    if raw['attachments'] and signals>=2:gate='Likely pass — attachment manifest and requirement signals recovered'
    elif raw['attachments'] or len(desc)>=300 or signals>=2:gate='Review — partial archive evidence recovered'
    else:gate='Fail / replace — insufficient recoverable requirement evidence'
    rec.update({'Description Recovered':'Yes' if desc else 'No','Attachment Count':len(raw['attachments']),'Attachment Names':'; '.join(a.get('filename','') for a in raw['attachments']),'Gate 7 Archive Result':gate,'Archive JSON':f"archive_enrichment_fast/{r['Intake ID']}_{notice}.json",'Errors':' | '.join(errs)})
    raw['description']=desc;raw['record']=rec
    (DEST/f"{r['Intake ID']}_{notice}.json").write_text(json.dumps(raw,indent=2)[:750000],encoding='utf-8')
    return rec

out=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(one,r):r for r in rows}
    for f in as_completed(fs):out.append(f.result())
out.sort(key=lambda x:x['Intake ID'])
with (OUT/'sam_archive_enriched_survivors.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary={'queried':len(out),'likely_pass':sum(x['Gate 7 Archive Result'].startswith('Likely') for x in out),'review':sum(x['Gate 7 Archive Result'].startswith('Review') for x in out),'fail_replace':sum(x['Gate 7 Archive Result'].startswith('Fail') for x in out),'description_recovered':sum(x['Description Recovered']=='Yes' for x in out),'attachment_manifest_recovered':sum(int(x['Attachment Count'])>0 for x in out),'records':out}
(OUT/'sam_archive_enriched_survivors_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
