import csv, html, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

DATA=Path(__file__).parent/'data'
ROLES=['communications','communication','public relations','brand','marketing','content strategy','employer branding','change management','organisational development','organizational development','stakeholder engagement']
SENIOR=['manager','lead','specialist','consultant','director','head','strategist','advisor','partner']
POS=[r'visa sponsorship (?:is |will be )?(?:available|provided|offered)',r'we (?:offer|provide) (?:visa |work permit )?sponsorship',r'visa sponsorship available',r'sponsor(?:ing)? (?:international )?(?:applicants|candidates)',r'relocation and visa support',r'work permit sponsorship provided']
NEG=[r'(?:no|not offering|without) (?:visa |work permit )?sponsorship',r'visa sponsorship (?:is )?not (?:available|provided|offered)',r'(?:must|need to) (?:already )?(?:have|possess) (?:the )?(?:right|authorization|authorisation) to work',r'cannot sponsor',r'unable to sponsor',r'will not sponsor',r'no sponsorship']
COUNTRY=['united states','usa','u.s.','new york','california','texas','chicago','seattle','boston','washington','united kingdom','london','manchester','bristol','england','scotland','ireland','dublin','germany','berlin','munich','hamburg','netherlands','amsterdam','rotterdam','france','paris','spain','madrid','barcelona','sweden','stockholm','denmark','copenhagen','norway','oslo','finland','helsinki','belgium','brussels','luxembourg','austria','vienna','portugal','lisbon','poland','warsaw','prague','czech','italy','milan','zurich','switzerland','europe','emea']
COLUMNS=['job_id','company','title','location','source','url','sponsorship','evidence','match_score','posted_or_updated','status','notes','description']

def clean(s):
    return BeautifulSoup(html.unescape(str(s or '')),'html.parser').get_text(' ',strip=True)

def get_json(url):
    res=requests.get(url,timeout=20,headers={'User-Agent':'VisaSponsorResearchAgent/1.0 (public-job-board-reader)','Accept':'application/json'})
    res.raise_for_status(); return res.json()

def boards():
    p=DATA/'boards.json'
    return json.loads(p.read_text()) if p.exists() else []

def scan_board(board):
    name,kind,slug=board['company'],board['platform'].lower(),board['slug'].strip()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',slug): raise ValueError('Invalid board slug')
    result=[]
    if kind=='greenhouse':
        payload=get_json(f'https://boards-api.greenhouse.io/v1/boards/{quote(slug)}/jobs?content=true')
        for x in payload.get('jobs',[]):
            result.append(dict(job_id=f'greenhouse:{slug}:{x["id"]}', company=name,title=x.get('title',''),location=(x.get('location') or {}).get('name',''),source='Greenhouse',url=x.get('absolute_url',''),description=clean(x.get('content','')),posted_or_updated=x.get('updated_at','')))
    elif kind=='lever':
        base='https://api.eu.lever.co' if board.get('region','global')=='eu' else 'https://api.lever.co'
        for offset in range(0,500,100):
            items=get_json(f'{base}/v0/postings/{quote(slug)}?mode=json&skip={offset}&limit=100')
            for x in items:
                cats=x.get('categories') or {}
                desc=' '.join([clean(x.get('descriptionPlain') or x.get('description')),clean(x.get('additionalPlain') or x.get('additional')),clean(' '.join(str(t.get('content','')) for t in x.get('lists',[]) if isinstance(t,dict)))])
                result.append(dict(job_id=f'lever:{slug}:{x["id"]}',company=name,title=x.get('text',''),location=cats.get('location',''),source='Lever',url=x.get('hostedUrl',''),description=desc,posted_or_updated=''))
            if len(items)<100: break
            time.sleep(.15)
    else: raise ValueError('Supported platforms: greenhouse or lever')
    return result

def sponsorship(desc):
    d=desc.lower()
    for pattern in NEG:
        m=re.search(pattern,d,re.I)
        if m: return 'Unavailable',d[max(0,m.start()-65):m.end()+90]
    for pattern in POS:
        m=re.search(pattern,d,re.I)
        if m: return 'Explicitly offered',d[max(0,m.start()-65):m.end()+90]
    if re.search(r'visa sponsorship|work permit sponsorship|sponsor',d,re.I):
        return 'Needs manual verification','Sponsorship mentioned, but the wording does not confirm availability for this role.'
    return 'Not stated','No explicit sponsorship statement detected in the job description.'

def evaluate(j):
    t=j['title'].lower();loc=j['location'].lower(); desc=j['description'].lower()
    title_role=any(term in t for term in ROLES)
    senior=any(term in t for term in SENIOR)
    relevant_geo=any(x in loc for x in COUNTRY)
    # Broad Europe / US only: location unknown still retained for manual triage
    sc,ev=sponsorship(desc)
    score=(55 if title_role else 0)+(15 if senior else 0)+(15 if relevant_geo else 0)+(15 if sc=='Explicitly offered' else 0)
    j.update(sponsorship=sc,evidence=ev,match_score=score,status='New',notes='')
    return j if title_role and (relevant_geo or not loc or 'remote' in loc) else None

def scan_all(board_list=None):
    out=[];errors=[]
    for board in (board_list if board_list is not None else boards()):
        try:
            for item in scan_board(board):
                tested=evaluate(item)
                if tested: out.append(tested)
        except (requests.RequestException,ValueError,KeyError,TypeError) as e:
            errors.append(f'{board.get("company","Unknown")}: {str(e)[:180]}')
    out.sort(key=lambda j: (j['sponsorship']=='Explicitly offered',j['match_score']),reverse=True)
    return out,errors

def write_csv(rows,path):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def read_csv(path):
    if not Path(path).exists():return []
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def merge(old,new):
    existing={x['job_id']:x for x in old}
    for j in new:
        if j['job_id'] in existing:
            j['status']=existing[j['job_id']].get('status','New')
            j['notes']=existing[j['job_id']].get('notes','')
        existing[j['job_id']]=j
    return list(existing.values())

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='jobs.csv');args=p.parse_args()
    rows,err=scan_all();write_csv(rows,args.output)
    print(f'Found {len(rows)} role-matched jobs; {len(err)} board errors; saved {args.output}')
    for e in err:print('WARN',e)
