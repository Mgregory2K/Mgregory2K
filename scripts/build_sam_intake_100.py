#!/usr/bin/env python3
import csv, json, re
from collections import Counter
from pathlib import Path

SRC = Path('data/green_gregory/sam_historical_open_2023_2024.csv')
OUT = Path('data/green_gregory')

EXCLUSION_TERMS = {
    'Food / perishables': ['food','fruit','vegetable','meat','milk','bread','produce','catering','meal','grocery','beverage'],
    'Medical / pharmaceutical': ['medical','pharmaceutical','drug','syringe','vaccine','patient','laboratory reagent','clinical'],
    'Fuel / petroleum': ['fuel','gasoline','diesel','petroleum','aviation fuel','lubricant'],
    'Hazardous chemical': ['hazmat','hazardous chemical','chemical disposal','pesticide','solvent','acid','sealant','adhesive'],
    'Construction / installation / repair / field service': ['construction','renovation','installation','install ','repair','maintenance service','grounds maintenance','janitorial service','landscaping','demolition','roofing','painting service'],
    'Rental / lease': ['rental','rent ','lease '],
    'Custom / personalized': ['custom manufacturing','custom fabricated','personalized','custom printing','embroidered'],
    'Safety-critical / defense platform': ['aircraft part','airframe','weapon','missile','flight critical','nuclear','armored vehicle'],
}

TRACK_TERMS = {
    'Office and facility consumables': ['office supplies','paper','toner','ink cartridge','envelope','binder','folder','janitorial supply','cleaning supplies','trash bag','tissue','paper towel','light bulb','lamp','battery'],
    'MRO tools and commercial hardware': ['tool','wrench','socket','drill','saw','cutter','fastener','bolt','screw','hardware','ladder','hose','valve','bearing','filter','pump','abrasive','sandpaper'],
    'Packaging, shipping, storage and containers': ['packaging','packing','shipping box','carton','container','pallet','crate','storage bin','plastic bag','stretch wrap','strapping','shipping supplies','label'],
    'Basic IT accessories and standard equipment': ['computer','monitor','keyboard','mouse','printer','scanner','network switch','router','ethernet','cable','headset','ups','laptop','tablet','webcam'],
}

RESTRICTED_SET_ASIDE = ['8(a)','8a ','hubzone','woman-owned','women-owned','wosb','edwosb','service-disabled','sdvosb','veteran-owned','vosb','indian economic','buy indian','local area']
MANDATORY_TERMS = ['abilityone','skilcraft','national industries for the blind','nib ','unicor','federal prison industries','mandatory source']
VEHICLE_TERMS = ['fair opportunity','only holders of','existing idiq','existing bpa','bpa holders','schedule holders','task order competition','delivery order competition']


def money(v):
    s = re.sub(r'[^0-9.\-]','',v or '')
    try: return float(s)
    except: return None


def classify_track(text):
    scores = {k:sum(1 for t in terms if t in text) for k,terms in TRACK_TERMS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'Mixed control'


def exclusion(text):
    for label, terms in EXCLUSION_TERMS.items():
        if any(t in text for t in terms):
            return label
    return 'Pass / no automatic exclusion detected'


def set_aside_fit(value):
    low = (value or '').lower()
    if any(t in low for t in RESTRICTED_SET_ASIDE):
        return 'No — socioeconomic set-aside not held by GGG'
    if not low or 'no set' in low or 'total small business' in low or 'small business set-aside' in low:
        return 'Potentially yes — subject to active SAM registration and representations'
    return 'Review — set-aside language requires validation'


def completeness(row):
    d = row.get('description','') or ''
    score = 0
    if len(d) >= 250: score += 1
    if re.search(r'\b(quantity|qty|each|ea|case|pack|unit|units|clin)\b', d.lower()): score += 1
    if re.search(r'\b(part number|model|brand name|specification|salient characteristics|nsn)\b', d.lower()): score += 1
    if row.get('additional_info'): score += 1
    if row.get('solicitation_number'): score += 1
    return ('Likely complete enough for archive review' if score >= 4 else
            'Partial — attachments or detail retrieval required' if score >= 2 else
            'Incomplete from extract')


def prelim_call(access, excl, complete, amount):
    if not access.startswith('Potentially yes') or not excl.startswith('Pass'):
        return 'Strikeout'
    if complete.startswith('Incomplete'):
        return 'Strikeout'
    if amount is None:
        return 'Double'
    if amount <= 5000:
        return 'Grand Slam' if complete.startswith('Likely') else 'Home Run'
    if amount <= 10000:
        return 'Home Run'
    if amount <= 25000:
        return 'Triple'
    if amount <= 50000:
        return 'Double'
    return 'Single'

with SRC.open(encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))

sample = [r for r in rows if (r.get('award_number') or r.get('awardee') or r.get('award_amount'))]
sample.sort(key=lambda r: (r.get('posted_date_parsed',''), r.get('notice_id','')))
assert len(sample) == 100, f'Expected 100 award-outcome records, found {len(sample)}'

out_rows = []
gate_counts = Counter()
tracks = Counter()
agencies = Counter()
for i, r in enumerate(sample, start=1):
    text = ((r.get('title') or '') + ' ' + (r.get('description') or '')).lower()
    track = classify_track(text)
    tracks[track] += 1
    agencies[r.get('agency') or 'Unknown'] += 1
    excl = exclusion(text)
    sa_fit = set_aside_fit(r.get('set_aside'))
    mandatory = 'Review required'
    if any(t in text for t in MANDATORY_TERMS): mandatory = 'Probable mandatory-source conflict'
    vehicle = any(t in text for t in VEHICLE_TERMS)
    open_path = 'No — vehicle-limited language detected' if vehicle else 'Potentially yes — direct solicitation notice'
    ggg_fit = sa_fit if not vehicle else 'No — parent/limited vehicle path detected'
    comp = completeness(r)
    amount = money(r.get('award_amount'))

    if vehicle:
        gate = 'Gate 3 — open competitive path'
    elif ggg_fit.startswith('No'):
        gate = 'Gate 4 — GGG eligibility'
    elif mandatory.startswith('Probable'):
        gate = 'Gate 5 — mandatory source'
    elif not excl.startswith('Pass'):
        gate = 'Gate 6 — product/service exclusion'
    elif comp.startswith('Incomplete'):
        gate = 'Gate 7 — requirement completeness'
    else:
        gate = 'Passes preliminary metadata gates — archive review required'
    gate_counts[gate] += 1

    access_score = 0 if vehicle else (85 if ggg_fit.startswith('Potentially yes') else 45)
    if mandatory.startswith('Probable'): access_score = 0
    fit_score = 0
    if excl.startswith('Pass'):
        fit_score = 50
        if track != 'Mixed control': fit_score += 15
        if comp.startswith('Likely'): fit_score += 15
        elif comp.startswith('Partial'): fit_score += 5
        if amount is not None and amount <= 10000: fit_score += 15
        elif amount is not None and amount <= 25000: fit_score += 8
        if amount is not None and amount > 50000: fit_score -= 15
    call = prelim_call(ggg_fit if not mandatory.startswith('Probable') else 'No', excl, comp, amount)
    decision = 'REVIEW' if gate.startswith('Passes') else 'NO-BID / REJECT AT INTAKE'

    pop = ', '.join(x for x in [r.get('city'),r.get('state'),r.get('zip'),r.get('country')] if x)
    award_outcome = 'Yes — embedded in official extract'
    source_url = r.get('historical_source_url') or r.get('record_link')
    notes = []
    if r.get('active') == 'Yes': notes.append('Extract Active flag inconsistent with 2023-2024 closed deadline; verify notice version/archive directly.')
    if not r.get('additional_info'): notes.append('No separate additional-information link in extract.')
    notes.append('Award outcome is answer key, not pre-award pricing evidence.')

    out_rows.append({
        'Intake ID':f'HOS01-{i:03d}',
        'Notice ID':r.get('notice_id',''),
        'Solicitation Number':r.get('solicitation_number',''),
        'Historical Source URL':source_url,
        'Notice Type':r.get('notice_type',''),
        'Posted Date':r.get('posted_date_parsed',''),
        'Original Response Deadline':r.get('response_deadline_parsed',''),
        'Agency':r.get('agency',''),
        'Subagency':r.get('subagency',''),
        'Contracting Office':r.get('contracting_office',''),
        'Title':r.get('title',''),
        'Description':(r.get('description','') or '')[:1200],
        'NAICS':r.get('naics',''),
        'PSC':r.get('psc',''),
        'Set-Aside Type':r.get('set_aside',''),
        'Estimated Value':'Unknown pre-award; historical award is answer key',
        'Product or Service':'Product' if excl.startswith('Pass') and 'service' not in text else 'Service / mixed',
        'Supply Track':track,
        'Place of Performance':pop,
        'Delivery Destination':pop or 'Not recovered from extract',
        'Attachments Available':'Yes / archive retrieval required' if r.get('additional_info') else 'Unknown / direct record review required',
        'Amendments Available':'Unknown — version history retrieval required',
        'Q&A Available':'Unknown — archive retrieval required',
        'Award Outcome Available':award_outcome,
        'Award Notice URL':source_url,
        'Awardee':r.get('awardee',''),
        'Award Amount':r.get('award_amount',''),
        'Award Type':'Not provided in extract outcome fields',
        'Parent Award ID':'Not indicated at solicitation intake',
        'Open Competitive Path':open_path,
        'Parent Vehicle Required':'Yes / probable' if vehicle else 'No evidence in extract; verify solicitation',
        'Could GGG Compete At Time':ggg_fit,
        'Mandatory-Source Status':mandatory,
        'AbilityOne Status':'Review exact product/NSN; no conflict detected' if mandatory == 'Review required' else mandatory,
        'Product-Exclusion Result':excl,
        'Requirement Completeness':comp,
        'Payment-Method Evidence':'Unknown — never infer from award amount',
        'Preliminary Supplier Exposure':'Not modeled before archive/requirements gate',
        'Exposure Classification':'Unclassified pending sourcing',
        'Preliminary Probable Net':'Not modeled before supplier pricing',
        'Preliminary Accessibility Score':access_score,
        'Preliminary Kickoff Fit Score':max(0,fit_score),
        'Preliminary Baseball Call':call,
        'Primary Failure Point':gate,
        'Intake Decision':decision,
        'Confidence':'Moderate — official extract metadata; attachments not yet reconstructed',
        'Notes':' '.join(notes),
        'Source Extract Row':r.get('source_extract_row',''),
    })

headers = list(out_rows[0])
with (OUT/'sam_intake_100.csv').open('w', encoding='utf-8', newline='') as f:
    w=csv.DictWriter(f, fieldnames=headers); w.writeheader(); w.writerows(out_rows)

for chunk_no in range(4):
    chunk = out_rows[chunk_no*25:(chunk_no+1)*25]
    with (OUT/f'sam_intake_100_part{chunk_no+1}.json').open('w',encoding='utf-8') as f:
        json.dump(chunk,f,indent=2)

summary = {
    'sample_method':'All 100 qualifying 2023-2024 solicitation/combined notices with embedded award outcome fields in the official SAM full CSV extract; deterministic sort by posted date then notice ID.',
    'sample_size':len(out_rows),
    'gate_counts':dict(gate_counts),
    'supply_tracks':dict(tracks),
    'top_agencies':agencies.most_common(15),
    'review_count':sum(1 for r in out_rows if r['Intake Decision']=='REVIEW'),
    'reject_count':sum(1 for r in out_rows if r['Intake Decision']!='REVIEW'),
    'baseball_calls':dict(Counter(r['Preliminary Baseball Call'] for r in out_rows)),
}
(OUT/'sam_intake_100_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
