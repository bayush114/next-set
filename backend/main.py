import os, re, uuid, json, time, secrets
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from html import unescape
import httpx
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import create_engine, Column, String, Integer, Text, select, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.exc import IntegrityError

STAGES=['Saved','Applied','Screen','Interview','Offer','Rejected','Withdrawn']
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class Job(Base):
 __tablename__='jobs'
 id=Column(String,primary_key=True); dedup=Column(String,unique=True,nullable=False); payload=Column(Text,nullable=False); version=Column(Integer,nullable=False,default=1)
class Run(Base):
 __tablename__='runs'
 id=Column(String,primary_key=True); payload=Column(Text,nullable=False)
class JobInput(BaseModel):
 company:str=Field(min_length=1,max_length=160); title:str=Field(min_length=1,max_length=200)
 location:str=Field(default='',max_length=200); url:str=Field(default='',max_length=2000); description:str=Field(default='',max_length=80000)
 salary_min:int|None=Field(default=None,ge=0,le=10000000); salary_max:int|None=Field(default=None,ge=0,le=10000000)
 currency:str=Field(default='USD',pattern='^[A-Z]{3}$'); compensation_note:str=Field(default='',max_length=1000)
 stage:str='Saved'; notes:str=Field(default='',max_length=20000); contact:str=Field(default='',max_length=300)
 next_action:str=Field(default='',max_length=1000); due:str=''; interview:str=''; priority:bool=False
 source:str=Field(default='manual',max_length=100); source_id:str=Field(default='',max_length=200)
 @model_validator(mode='after')
 def check(self):
  self.company=self.company.strip();self.title=self.title.strip()
  if not self.company or not self.title: raise ValueError('Company and title required')
  if self.stage not in STAGES: raise ValueError('Invalid stage')
  if self.url and not re.match(r'^https?://[^\s]+$',self.url): raise ValueError('Use an http or https URL')
  if self.salary_min is not None and self.salary_max is not None and self.salary_min>self.salary_max: raise ValueError('Salary range is reversed')
  for v in [self.due,self.interview]:
   if v:
    d=datetime.fromisoformat(v.replace('Z','+00:00'))
    if not d.tzinfo:raise ValueError('Dates must include timezone')
  return self
class Edit(JobInput): version:int=Field(ge=1)
class Ingest(BaseModel): board:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')

def key(d):
 if d['source_id']:return d['source'].lower()+':'+d['source_id']
 if d['url']:return d['url'].split('?')[0].rstrip('/').lower()
 return '|'.join(re.sub(r'\s+',' ',d[x].strip().lower()) for x in ['company','title','location'])
def rank(d):
 text=(d['title']+' '+d['description']).lower();score=0; reasons=[]
 if re.search(r'\b(senior|staff|principal|lead|director)\b',d['title'],re.I):score-=40;reasons.append('Title indicates senior-level expectations')
 if re.search(r'\b(backend|back.end|infrastructure|platform|distributed)\b',text):score+=30;reasons.append('Backend / infrastructure terms in posting')
 if re.search(r'\b(software|engineer|developer)\b',d['title'],re.I):score+=15;reasons.append('Engineering role title')
 years=re.findall(r'\b(\d{1,2})\+?\s*(?:years|yrs)',text)
 if years and max(map(int,years))>3:score-=20;reasons.append('Posting mentions more than 3 years; review requirements')
 if re.search(r'security clearance|top secret',text):score-=50;reasons.append('Clearance language: review eligibility')
 if d['currency']=='USD' and d['salary_max'] is not None:
  if d['salary_max']>=180000:score+=25;reasons.append('Stated pay ceiling reaches $180k; not a guaranteed offer')
 else:reasons.append('Comparable USD pay unknown')
 if any(x in d['location'].lower() for x in ['new york','nyc','austin','remote']):score+=15;reasons.append('Preferred location or remote')
 return {'score':max(0,min(100,score)), 'reasons':reasons}
def view(row):return {**json.loads(row.payload),'id':row.id,'version':row.version}
def create_app(url=None,token=None):
 engine=create_engine(url or os.getenv('DATABASE_URL','sqlite:///./jobs.db'),connect_args={'check_same_thread':False} if (url or os.getenv('DATABASE_URL','sqlite:///./jobs.db')).startswith('sqlite') else {})
 secret=token if token is not None else os.getenv('APP_TOKEN','')
 @asynccontextmanager
 async def lifespan(app):
  if not secret:raise RuntimeError('Set APP_TOKEN before starting; API refuses unauthenticated use')
  Base.metadata.create_all(engine)
  yield
  engine.dispose()
 app=FastAPI(title='Job Compass',lifespan=lifespan)
 def auth(authorization:str=Header(default='')):
  if not secret or not secrets.compare_digest(authorization,'Bearer '+secret):raise HTTPException(401,'Authentication required')
 def db():
  with Session(engine) as s:yield s
 @app.get('/api/health')
 def health():return {'status':'ok'}
 @app.get('/api/jobs',dependencies=[Depends(auth)])
 def jobs(s:Session=Depends(db)):return sorted([view(x) for x in s.scalars(select(Job))],key=lambda x:x['updated_at'],reverse=True)
 @app.post('/api/jobs',dependencies=[Depends(auth)],status_code=201)
 def add(data:JobInput,s:Session=Depends(db)):
  d=data.model_dump(); d.update(created_at=now(),updated_at=now(),history=[{'at':now(),'stage':d['stage']}]);d['rank']=rank(d)
  row=Job(id=str(uuid.uuid4()),dedup=key(d),payload=json.dumps(d),version=1);s.add(row)
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'This posting is already tracked')
  return view(row)
 @app.put('/api/jobs/{id}',dependencies=[Depends(auth)])
 def update(id:str,data:Edit,s:Session=Depends(db)):
  row=s.get(Job,id)
  if not row:raise HTTPException(404,'Job not found')
  old=view(row)
  if data.version!=row.version:raise HTTPException(409,'Changed in another tab. Reload before saving.')
  d=data.model_dump(exclude={'version'});d.update(created_at=old['created_at'],updated_at=now(),history=old['history'])
  if d['stage']!=old['stage']:d['history'].append({'at':now(),'stage':d['stage']})
  d['rank']=rank(d)
  result=s.query(Job).filter(Job.id==id,Job.version==data.version).update({'payload':json.dumps(d),'dedup':key(d),'version':data.version+1})
  if not result:s.rollback();raise HTTPException(409,'Concurrent edit; reload')
  try:s.commit()
  except IntegrityError:s.rollback();raise HTTPException(409,'Duplicate posting')
  return view(s.get(Job,id))
 @app.get('/api/export',dependencies=[Depends(auth)])
 def export(s:Session=Depends(db)):return {'version':1,'jobs':[view(x) for x in s.scalars(select(Job))]}
 @app.get('/api/runs',dependencies=[Depends(auth)])
 def runs(s:Session=Depends(db)):return sorted([json.loads(x.payload) for x in s.scalars(select(Run))],key=lambda x:x['started_at'],reverse=True)[:50]
 @app.post('/api/ingest',dependencies=[Depends(auth)])
 def ingest(data:Ingest,s:Session=Depends(db)):
  report={'id':str(uuid.uuid4()),'board':data.board,'started_at':now(),'status':'running','added':0,'existing':0,'attempts':0,'error':None}
  row=Run(id=report['id'],payload=json.dumps(report));s.add(row);s.commit()
  try:
   payload=None
   with httpx.Client(timeout=20,follow_redirects=False) as client:
    for attempt in range(3):
     report['attempts']=attempt+1
     try:
      response=client.get(f'https://boards-api.greenhouse.io/v1/boards/{data.board}/jobs?content=true')
      response.raise_for_status();payload=response.json();break
     except (httpx.TimeoutException,httpx.NetworkError,httpx.HTTPStatusError) as exc:
      if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code not in [429,500,502,503,504]:raise
      if attempt==2:raise
      time.sleep(2**attempt)
   if not isinstance(payload,dict) or not isinstance(payload.get('jobs'),list):raise ValueError('Unexpected source response')
   # Validate complete source response before writing; failed fetches never close jobs.
   normalized=[]
   for x in payload['jobs']:
    d=JobInput(company=data.board,title=x['title'],location=x.get('location',{}).get('name',''),url=x['absolute_url'],description=unescape(re.sub('<[^>]+>',' ',x.get('content',''))),source='greenhouse:'+data.board.lower(),source_id=str(x['id'])).model_dump();normalized.append(d)
   for d in normalized:
    existing=s.scalar(select(Job).where(Job.dedup==key(d)))
    if existing:report['existing']+=1;continue
    d.update(created_at=now(),updated_at=now(),history=[{'at':now(),'stage':'Saved'}]);d['rank']=rank(d)
    # Savepoint protects the run when concurrent imports encounter the same posting.
    try:
     with s.begin_nested():s.add(Job(id=str(uuid.uuid4()),dedup=key(d),payload=json.dumps(d),version=1));s.flush()
     report['added']+=1
    except IntegrityError:report['existing']+=1
   report['status']='succeeded';s.commit()
  except Exception as exc:
   s.rollback();report.update(status='failed',added=0,error=str(exc)[:500])
  report['finished_at']=now();row=s.get(Run,report['id']);row.payload=json.dumps(report);s.commit();return report
 if os.path.isdir('dist'):app.mount('/',StaticFiles(directory='dist',html=True),name='frontend')
 return app
app=create_app()
