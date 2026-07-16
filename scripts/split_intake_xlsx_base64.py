#!/usr/bin/env python3
import base64,json
from pathlib import Path
src=Path('data/green_gregory/GGG_Historical_Open_Solicitation_Intake_Test01.xlsx')
out=Path('data/green_gregory/xlsx_base64_parts');out.mkdir(parents=True,exist_ok=True)
for p in out.glob('part_*.txt'):p.unlink()
s=base64.b64encode(src.read_bytes()).decode('ascii')
chunk=12000
parts=[s[i:i+chunk] for i in range(0,len(s),chunk)]
for i,p in enumerate(parts,1):(out/f'part_{i:02d}.txt').write_text(p,encoding='ascii')
(out/'manifest.json').write_text(json.dumps({'source':str(src),'base64_length':len(s),'chunk_size':chunk,'part_count':len(parts)},indent=2),encoding='utf-8')
print(len(parts),len(s))
