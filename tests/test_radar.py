from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.radar import canonical_post,evidence,discover

NOW=datetime(2026,11,8,tzinfo=timezone.utc)
ACTIVITY=(int(NOW.timestamp()*1000)<<22)
URL=f'https://www.linkedin.com/posts/recruiter_hiring-activity-{ACTIVITY}-abcd?tracking=x'
HIT={'url':URL,'title':'Hiring Backend Software Engineer II NYC','text':'Our team is hiring Python engineers, 1-3 years experience.'}

def test_url_dedup_and_date():
 a=canonical_post(URL)
 assert a==canonical_post(a)
 lead=evidence(HIT,current=NOW)
 assert lead['published_at']==NOW.isoformat()
 assert lead['score']>=80
 assert evidence(HIT,current=datetime(2026,12,8,tzinfo=timezone.utc)) is None

@pytest.mark.parametrize('url',['https://linkedin.com.evil/posts/a','https://evil.com/posts/a','http://linkedin.com/posts/a','https://linkedin.com/in/recruiter','https://linkedin.com/posts/no-id'])
def test_reject_other_urls(url):
 with pytest.raises(ValueError):canonical_post(url)

def test_ingestion_preserves_notes_and_evidence(tmp_path,monkeypatch):
 lead=evidence(HIT,current=NOW)
 monkeypatch.setattr('backend.main.discover',lambda:{'leads':[lead], 'errors':[], 'raw_results':1,'filtered_out':0,'provider':'test','coverage':'Public only'})
 with TestClient(create_app('sqlite:///'+str(tmp_path/'db'),'secret')) as c:
  assert c.post('/api/radar/scan').status_code==401
  c.headers['Authorization']='Bearer secret'
  assert c.post('/api/radar/scan').json()['added']==1
  j=c.get('/api/radar').json()[0];j.update(notes='Keep personal notes',stage='Applied')
  assert c.put('/api/jobs/'+j['id'],json=j).status_code==200
  assert c.post('/api/radar/scan').json()['existing']==1
  saved=c.get('/api/radar').json()[0]
  assert saved['notes']=='Keep personal notes' and saved['radar']['url']==lead['url']

def test_source_failure_is_not_empty_success(monkeypatch):
 monkeypatch.delenv('ALL_PROXY',raising=False)
 monkeypatch.delenv('HTTPS_PROXY',raising=False)
 monkeypatch.delenv('HTTP_PROXY',raising=False)
 def fail(*a,**kw):raise RuntimeError('provider unavailable')
 class Client:
  def __init__(self,**kw):pass
  def __enter__(self):return self
  def __exit__(self,*a):pass
 monkeypatch.setattr('backend.radar.httpx.Client',Client)
 monkeypatch.setattr('backend.radar.request',fail)
 r=discover();assert len(r['errors'])==6 and not r['leads']


def test_brave_adapter_filters_and_deduplicates(monkeypatch):
 import httpx
 monkeypatch.setenv('BRAVE_SEARCH_API_KEY','test-not-real')
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return NOW
 monkeypatch.setattr('backend.radar.datetime',Clock)
 class Client:
  def __init__(self,**kw):pass
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def get(self,url,**kw):
   assert kw['headers']['X-Subscription-Token']=='test-not-real'
   return httpx.Response(200,json={'web':{'results':[{'url':URL,'title':HIT['title'],'description':HIT['text']}]}},request=httpx.Request('GET',url))
 monkeypatch.setattr('backend.radar.httpx.Client',Client)
 result=discover()
 assert len(result['leads'])==1 and not result['errors'] and result['raw_results']==6
