#!/usr/bin/env python3
import csv, json, re, urllib.request
from collections import Counter
from datetime import datetime, date
from pathlib import Path

URL = 'https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv'
OUT = Path('data/green_gregory')
OUT.mkdir(parents=True, exist_ok=True)
RAW = OUT / 'ContractOpportunitiesFullCSV.csv'


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def parse_date(v):
    v = (v or '').strip().replace('Z','')
    if not v:
        return None
    candidates = [v, v[:10], v.split('T')[0], v.split(' ')[0]]
    fmts = ['%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%Y/%m/%d','%Y-%m-%d %H:%M:%S']
    for c in candidates:
        for f in fmts:
            try:
                return datetime.strptime(c, f).date()
            except Exception:
                pass
    return None

urllib.request.urlretrieve(URL, RAW)
with RAW.open('r', encoding='utf-8-sig', errors='replace', newline='') as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames or []
    keymap = {norm(x): x for x in fields}
    aliases = {
        'notice_id':['noticeid'], 'title':['title'],
        'solicitation_number':['sol','solicitationnumber','solicitationno','solicitation'],
        'agency':['departmentindagency','fullparentpathname','departmentagency','agency','department'],
        'subagency':['subtier'], 'contracting_office':['office'],
        'posted_date':['posteddate'], 'notice_type':['type','noticetype'], 'base_type':['basetype'],
        'archive_type':['archivetype'], 'archive_date':['archivedate'],
        'set_aside':['setaside','typeofsetasidedescription'], 'set_aside_code':['setasidecode','typeofsetaside'],
        'response_deadline':['responsedeadline','responseduedate'],
        'naics':['naicscode','naics'], 'psc':['classificationcode','psc'], 'active':['active'],
        'description':['description'], 'additional_info':['additionalinfolink'], 'record_link':['link'],
        'award_number':['awardnumber'], 'award_amount':['award','awardamount'],
        'awardee':['awardee'], 'award_date':['awarddate'],
        'city':['popcity'], 'state':['popstate'], 'zip':['popzip'], 'country':['popcountry'],
    }
    resolved = {dst: next((keymap[o] for o in opts if o in keymap), None) for dst, opts in aliases.items()}
    counts = Counter(); type_values = Counter(); active_values = Counter()
    solicitation_rows = []; award_rows = []
    allowed = {'solicitation','combinedsynopsissolicitation'}
    for source_row, row in enumerate(reader, start=2):
        counts['total_rows'] += 1
        def get(k):
            col = resolved.get(k); return (row.get(col,'') if col else '').strip()
        pd = parse_date(get('posted_date'))
        typ = norm(get('notice_type'))
        if pd and date(2023,1,1) <= pd <= date(2025,12,31):
            type_values[get('notice_type') or '(blank)'] += 1
            if typ == 'awardnotice' or get('award_number') or get('awardee') or get('award_amount'):
                c = {k:get(k) for k in aliases}; c['source_extract_row']=source_row
                c['posted_date_parsed']=pd.isoformat(); c['award_date_parsed']=(parse_date(get('award_date')) or date.min).isoformat() if get('award_date') else ''
                c['historical_source_url']=get('record_link') or (f"https://sam.gov/opp/{get('notice_id')}/view" if get('notice_id') else '')
                award_rows.append(c); counts['award_index_rows'] += 1
        if not pd or not (date(2023,1,1) <= pd <= date(2024,12,31)):
            continue
        counts['posted_2023_2024'] += 1
        if typ not in allowed:
            continue
        counts['actual_solicitation_type'] += 1
        rd = parse_date(get('response_deadline'))
        if not rd:
            counts['missing_response_deadline'] += 1; continue
        if rd > date(2024,12,31):
            counts['deadline_after_boundary'] += 1; continue
        counts['deadline_closed_by_2024_12_31'] += 1
        ad = parse_date(get('archive_date')); active_values[get('active') or '(blank)'] += 1
        c = {k:get(k) for k in aliases}; c['source_extract_row']=source_row
        c['historical_source_url']=get('record_link') or (f"https://sam.gov/opp/{get('notice_id')}/view" if get('notice_id') else '')
        c['posted_date_parsed']=pd.isoformat(); c['response_deadline_parsed']=rd.isoformat(); c['archive_date_parsed']=ad.isoformat() if ad else ''
        c['historical_status_basis']='Response deadline passed no later than 2024-12-31; notice version and archive status require direct verification.'
        solicitation_rows.append(c); counts['solicitation_universe_rows'] += 1

sol_cols = list(aliases)+['source_extract_row','historical_source_url','posted_date_parsed','response_deadline_parsed','archive_date_parsed','historical_status_basis']
with (OUT/'sam_historical_open_2023_2024.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=sol_cols); w.writeheader(); w.writerows(solicitation_rows)
award_cols = list(aliases)+['source_extract_row','posted_date_parsed','award_date_parsed','historical_source_url']
with (OUT/'sam_award_notice_index_2023_2025.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=award_cols); w.writeheader(); w.writerows(award_rows)

profile={'source_url':URL,'retrieved_utc':datetime.utcnow().isoformat()+'Z','raw_columns':fields,'resolved_columns':resolved,'counts':dict(counts),'active_values_among_selected':dict(active_values),'notice_types_2023_2025':dict(type_values),'method_note':'Active is retained but not controlling. Historical gate uses response deadline plus direct archive/version verification. Solicitation sampling is independent of outcome availability.'}
(OUT/'sam_extract_profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
print(json.dumps(profile,indent=2))
