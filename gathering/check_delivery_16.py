#!/usr/bin/env python3
"""Validate round 16 packaging offline, without editing any line."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared/wall-thumbnail'))
import thumbnail


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.section=None;self.orders={};self.articles=0;self.images=[];self.capture=False;self.heading='';self.scripts=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='section': self.section=a['id'];self.orders[self.section]=[]
        if tag=='article':self.articles+=1
        if tag=='img':self.images.append(a['src'])
        if tag=='script':self.scripts+=1
        if tag=='h3':self.capture=True;self.heading=''
    def handle_data(self,data):
        if self.capture:self.heading+=data
    def handle_endtag(self,tag):
        if tag=='h3':
            hit=re.match(r'Round ([0-9]+)',self.heading)
            if hit and self.section:self.orders[self.section].append(int(hit[1]))
            self.capture=False
        if tag=='section':self.section=None


def jpeg_size(raw):
    assert raw[:2]==b'\xff\xd8' and raw[-2:]==b'\xff\xd9'
    at=2
    while at<len(raw):
        assert raw[at]==255
        marker=raw[at+1];length=int.from_bytes(raw[at+2:at+4],'big')
        if marker==0xc0:
            depth,h,w,channels=struct.unpack('>BHHB',raw[at+4:at+10]);assert depth==8 and channels==3
            return w,h
        at+=length+2
    raise ValueError('baseline JPEG frame missing')


def git(*args):
    return subprocess.run(['git',*args],capture_output=True,text=True,check=True).stdout.splitlines()


def main():
    wall=Path('artifacts/gathering/wall-v16.png');raw=wall.read_bytes()
    w,h,rows=thumbnail.png_rgb(wall);assert (w,h)==(1254,1254)
    assert Path('artifacts/gathering/wall.png').read_bytes()==raw
    digest=hashlib.sha256(raw).hexdigest()
    jpg=Path('dist/gathering/16.jpg').read_bytes();assert jpeg_size(jpg)==(512,512) and len(jpg)<100000
    record=json.loads(Path('dist/gathering/16.json').read_text())
    assert set(record)=={'name','image','attributes'}
    assert record['image']=='https://api.imd.fun/artifacts/'+digest
    assert record['name']=='The Measured Balance'
    traits=record['attributes']
    assert [t['trait_type'] for t in traits]==['Cave','Wall','Number','Left behind','Meaning','One thing']
    assert all(set(t)=={'trait_type','value'} for t in traits)
    assert [t['value'] for t in traits[:3]]==['Moss','Gathering',16] and type(traits[2]['value']) is int
    assert traits[3]['value']=='Shared Return Relations and Code Context' and traits[-1]['value']=='Gathering'
    assert json.loads(Path('dist/goals.json').read_text())==[{'line':n,'goal':Path(f'line-{n}/GOAL.md').read_text().strip()} for n in range(1,5)]
    records=list(Path('dist').glob('*/[0-9][0-9].json'));painted=pending=0
    bare='https://api.imd.fun/artifacts/250525790c1987cbb52114bd4e77926f023ac1dc10b73ffc2e1f56e32dfb8a36'
    for p in records:
        r=json.loads(p.read_text())
        if r['name']=='Not painted yet':
            pending+=1;assert r=={'name':'Not painted yet','image':bare,'attributes':[{'trait_type':'Cave','value':'Moss'}]}
            assert not p.with_suffix('.jpg').exists()
        else:
            painted+=1;assert p.with_suffix('.jpg').is_file()
    assert (len(records),painted,pending)==(165,80,85)
    for slug in ['line-1','line-2','line-3','line-4','gathering']:
        assert all(Path(f'dist/{slug}/{n:02}.json').is_file() for n in range(2,22))
    assert all(json.loads(Path(f'dist/gathering/{n:02}.json').read_text())['name']=='Not painted yet' for n in range(17,22))
    page=Page();page.feed(Path('dist/index.html').read_text());assert page.articles==len(records) and not page.scripts
    for slug,order in page.orders.items():
        expected=[int(p.stem) for p in sorted(Path('dist',slug).glob('[0-9][0-9].json'),reverse=True) if json.loads(p.read_text())['name']!='Not painted yet']
        assert order[:len(expected)]==expected
    assert all(s.startswith('https://api.imd.fun/artifacts/') or (Path('dist')/s).is_file() for s in page.images)
    visual=json.loads(Path('gathering/visual-checks-16.json').read_text())
    assert visual['output_sha256']==digest and visual['changed_pixels_outside_addition']==0
    assert visual['source_sha256']==json.loads(Path('dist/gathering/15.json').read_text())['image'].rsplit('/',1)[1]
    assert visual['left_hand_digits']==visual['right_hand_digits']==5 and visual['new_hands']==0
    assert not visual['unmet_visual_requirements_observed']
    checks=json.loads(Path('gathering/check-results-16.json').read_text())
    assert checks['all_passed'] and all(c['passed'] for c in checks['checks'])
    count=sum(c.get('test_count',0) for c in checks['checks']);assert count==1102 and len(checks['checks'])==159
    demo=json.loads(Path('shared/return-relations/demo-result.json').read_text());assert demo['verdict']=='consistent'
    bridge=json.loads(Path('shared/return-relations/surface-demo-result.json').read_text())
    assert bridge['verdict']=='withheld' and bridge['decoded_calls'] is None and bridge['relations'] is None
    provenance=json.loads(Path('shared/return-relations/provenance.json').read_text())
    for row in provenance['files']:
        assert hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()==row['source_sha256']
        assert hashlib.sha256(Path(row['copy']).read_bytes()).hexdigest()==row['copy_sha256']
    changed=git('diff','HEAD','--name-only')+git('ls-files','--others','--exclude-standard')
    assert all(p.startswith(('gathering/','shared/','dist/','artifacts/gathering/')) for p in changed),changed
    assert not any(p.startswith('dist/line-') for p in changed)
    assert not git('ls-files',str(wall))
    oversized=[str(p) for root in ('gathering','shared','dist') for p in Path(root).rglob('*') if p.is_file() and p.stat().st_size>100000]
    assert not oversized,oversized
    assert Path('gathering/COINS.md').read_text().splitlines()[0]=='none'
    assert not Path('gathering/coin-order.json').exists() and not Path('gathering/deploy-order.json').exists()
    result={'schema':'gathering-delivery-checks-v16','authority':'Local contributor checks; no independent certification.',
            'wall':{'path':str(wall),'width':w,'height':h,'format':'PNG RGB 8-bit','sha256':digest,'bytes':len(raw),'required_png_untracked':True},
            'thumbnail':{'path':'dist/gathering/16.jpg','width':512,'height':512,'format':'baseline JPEG','bytes':len(jpg)},
            'visual':visual,'offline_commands':len(checks['checks']),'offline_tests':count,'expected_exits_match':True,
            'records':len(records),'painted':painted,'placeholders':pending,'gallery_articles':page.articles,
            'goals':4,'line_sources_and_records_unchanged':True,'oversized_source_files':oversized,
            'shared_relation_demo':'consistent','shared_bridge_demo':'withheld: different historical blocks',
            'live_spender_code':'two runtimes present at exact inventory block',
            'live_pool_attempts':'finalized and latest refused: RPC 4444 pruned history unavailable'}
    Path('gathering/delivery-checks-16.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
