import pytest,httpx
from fastapi.testclient import TestClient
from backend.main import create_app,rank
@pytest.fixture
def client(tmp_path):
 with TestClient(create_app('sqlite:///'+str(tmp_path/'test.db'),'test-token')) as c:
  c.headers['Authorization']='Bearer test-token';yield c

def job(**kw):return dict(company='Example',title='Backend Engineer',location='NYC',salary_max=200000,**kw)
def test_auth(client):
 assert client.get('/api/jobs',headers={'Authorization':''}).status_code==401
 assert client.get('/api/jobs').json()==[]
def test_create_duplicate_and_export(client):
 assert client.post('/api/jobs',json=job()).status_code==201
 assert client.post('/api/jobs',json=job()).status_code==409
 assert len(client.get('/api/export').json()['jobs'])==1
def test_validation(client):
 for payload in [job(url='javascript:alert(1)'),job(stage='Fake'),job(salary_min=300000),job(interview='2026-11-01T10:00:00')]:assert client.post('/api/jobs',json=payload).status_code==422
 assert client.get('/api/jobs').json()==[]
def test_update_history_conflict(client):
 j=client.post('/api/jobs',json=job()).json();j['stage']='Interview';j['notes']='Private prep'
 assert client.put('/api/jobs/'+j['id'],json=j).status_code==200
 assert client.put('/api/jobs/'+j['id'],json=j).status_code==409
 saved=client.get('/api/jobs').json()[0];assert saved['notes']=='Private prep';assert [x['stage'] for x in saved['history']]==['Saved','Interview']
def test_ranking(client):
 j=client.post('/api/jobs',json=job()).json();assert j['rank']['score']==85
 j['title']='Senior Platform Engineer';j['description']='Requires 8 years and security clearance';assert rank(j)['score']==0

class FakeSource:
 def __init__(self,*a,**kw):pass
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def get(self,url):return httpx.Response(200,json={'jobs':[{'id':7,'title':'Platform Engineer','absolute_url':'https://example.com/7','content':'<p>Build systems</p>','location':{'name':'NYC'}}]},request=httpx.Request('GET',url))
def test_ingestion_idempotent_preserves_edits(client,monkeypatch):
 monkeypatch.setattr('backend.main.httpx.Client',FakeSource)
 assert client.post('/api/ingest',json={'board':'example'}).json()['added']==1
 j=client.get('/api/jobs').json()[0];j.update(stage='Applied',notes='Keep this');client.put('/api/jobs/'+j['id'],json=j)
 assert client.post('/api/ingest',json={'board':'example'}).json()['existing']==1
 assert client.get('/api/jobs').json()[0]['notes']=='Keep this'
 assert len(client.get('/api/runs').json())==2
def test_ingestion_failure_visible_and_no_partial_data(client,monkeypatch):
 class Bad(FakeSource):
  def get(self,url):return httpx.Response(404,request=httpx.Request('GET',url))
 monkeypatch.setattr('backend.main.httpx.Client',Bad)
 r=client.post('/api/ingest',json={'board':'missing'}).json();assert r['status']=='failed';assert r['attempts']==1
 assert client.get('/api/jobs').json()==[];assert client.get('/api/runs').json()[0]['error']
def test_transient_retries(client,monkeypatch):
 class Retry(FakeSource):
  calls=0
  def get(self,url):
   self.calls+=1
   return httpx.Response(503,request=httpx.Request('GET',url)) if self.calls<3 else super().get(url)
 monkeypatch.setattr('backend.main.httpx.Client',Retry);monkeypatch.setattr('backend.main.time.sleep',lambda _:None)
 r=client.post('/api/ingest',json={'board':'example'}).json();assert r['attempts']==3;assert r['status']=='succeeded'
def test_board_cannot_target_arbitrary_urls(client):
 assert client.post('/api/ingest',json={'board':'http://localhost/admin'}).status_code==422
