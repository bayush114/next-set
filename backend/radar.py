"""Public hiring-post discovery. Search evidence is never a verified job opening."""
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree
import httpx

QUERIES = [
 'site:linkedin.com/posts hiring ("software engineer" OR "backend engineer") ("New York" OR NYC)',
 'site:linkedin.com/posts hiring ("machine learning" OR MLOps OR "AI engineer")',
 'site:linkedin.com/posts hiring ("data scientist" OR "data engineer") (NYC OR remote)',
 'site:linkedin.com/posts hiring ("engineer II" OR "early career" OR "1-3 years")',
 'site:linkedin.com/posts hiring (engineer OR developer) (Austin OR Chicago OR Miami OR "San Francisco")',
 'site:linkedin.com/posts ("my team" OR "we are hiring") ("full stack" OR "forward deployed")',
]

def canonical_post(url):
 p = urlsplit(url)
 if p.scheme != 'https' or not (p.hostname == 'linkedin.com' or (p.hostname or '').endswith('.linkedin.com')):
  raise ValueError('Use a public LinkedIn post URL')
 if not (p.path.startswith('/posts/') or p.path.startswith('/feed/update/')):
  raise ValueError('Use a post URL, not a profile or jobs search page')
 match = re.search(r'(?:activity-|urn:li:activity:)(\d{18,20})', p.path)
 if not match:
  raise ValueError('Post URL must contain a LinkedIn activity ID')
 return urlunsplit(('https','www.linkedin.com', '/feed/update/urn:li:activity:'+match[1]+'/', '', ''))

def post_date(url):
 activity = re.search(r'activity:(\d+)', canonical_post(url))[1]
 # LinkedIn activity IDs encode a millisecond creation time in their high bits.
 return datetime.fromtimestamp((int(activity) >> 22)/1000, timezone.utc)

def evidence(hit, days=14, current=None):
 url = canonical_post(hit['url'])
 published = post_date(url)
 current = current or datetime.now(timezone.utc)
 age = (current-published).total_seconds()/86400
 if age < -1 or age > days:
  return None
 title = str(hit.get('title',''))[:200]
 text = str(hit.get('text',''))[:12000]
 combined = title+' '+text
 if not re.search(r'hiring|recruiting|open role|join (?:us|my|our)|looking for',combined,re.I):
  return None
 if not re.search(r'engineer|developer|data scien|MLOps',combined,re.I):
  return None
 flags=[]; score=35
 if re.search(r'early.career|junior|engineer ii|[012]\s*[-–]\s*[234]\s*years',combined,re.I):score+=25
 if re.search(r'new york|\bNYC\b',combined,re.I):score+=20
 elif re.search(r'austin|san francisco|chicago|miami|remote',combined,re.I):score+=10
 if re.search(r'backend|platform|infrastructure|python|java|typescript|react|SQL',combined,re.I):score+=15
 if re.search(r'\b(staff|principal|director|VP)\b|[5-9]\+?\s*years',combined,re.I):score-=50;flags.append('Potential seniority mismatch')
 elif re.search(r'\bsenior\b',combined,re.I):score-=25;flags.append('Senior role: review requirements')
 if re.search(r'intern(?:ship)?\b',combined,re.I):score-=40;flags.append('May be an internship')
 flags+=['Opening, employer, compensation and work arrangement not independently verified']
 return dict(url=url,title=title or 'Hiring post',text=text,published_at=published.isoformat(),
             date_basis='LinkedIn activity ID creation timestamp; reposted content may be older',
             discovered_at=current.isoformat(),score=max(0,min(100,score)),flags=flags,
             status='search_evidence',provider=hit.get('provider','manual'))

def request(client,url,**kwargs):
 for attempt in range(3):
  try:
   response=client.get(url,**kwargs);response.raise_for_status();return response
  except (httpx.TimeoutException,httpx.NetworkError,httpx.HTTPStatusError) as exc:
   if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code not in (429,500,502,503,504):raise
   if attempt==2:raise
   time.sleep(2**attempt)

def discover(days=14):
 """Bing RSS needs no credential; optional Brave key improves search control."""
 hits=[];errors=[];key=os.getenv('BRAVE_SEARCH_API_KEY','')
 provider='brave' if key else 'bing_rss'
 with httpx.Client(timeout=20,follow_redirects=False) as client:
  for q in QUERIES:
   try:
    if key:
     data=request(client,'https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':20,'freshness':'pw'},headers={'X-Subscription-Token':key}).json()
     batch=[{'url':x['url'],'title':x.get('title',''),'text':x.get('description','')} for x in data.get('web',{}).get('results',[])]
    else:
     root=ElementTree.fromstring(request(client,'https://www.bing.com/search',params={'q':q,'format':'rss'}).text)
     batch=[{'url':x.findtext('link',''),'title':x.findtext('title',''),'text':x.findtext('description','')} for x in root.findall('./channel/item')]
    hits.extend(dict(x,provider=provider) for x in batch)
   except Exception:
    # Never persist provider exceptions containing credentials or request headers.
    errors.append({'query':q,'error':'Search provider request failed'})
 leads={}; rejected=0
 for hit in hits:
  try:lead=evidence(hit,days)
  except (ValueError,OverflowError,OSError):lead=None
  if lead:leads[lead['url']]=lead
  else:rejected+=1
 return {'provider':provider,'leads':sorted(leads.values(),key=lambda x:x['score'],reverse=True),
         'errors':errors,'raw_results':len(hits),'filtered_out':rejected,
         'coverage':'Public search index only; empty results do not mean no LinkedIn openings.'}
