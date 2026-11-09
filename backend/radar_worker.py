"""Optional persistent scan worker: python -m backend.radar_worker."""
import os
import time
import httpx

def main():
 token=os.environ['APP_TOKEN']
 interval=max(3600,int(os.getenv('RADAR_INTERVAL_SECONDS','21600')))
 origin=os.getenv('RADAR_API_ORIGIN','http://app:8000').rstrip('/')
 if not origin.startswith(('http://','https://')):raise ValueError('Invalid API origin')
 while True:
  delay=interval
  try:
   with httpx.Client(timeout=600) as client:
    r=client.post(origin+'/api/radar/scan',headers={'Authorization':'Bearer '+token});r.raise_for_status()
    result=r.json();print('Radar:',result['status'],'added:',result['added'],flush=True)
  except (httpx.HTTPError,ValueError):
   delay=60
   print('Radar API unavailable; retrying in one minute. Check server scan history.',flush=True)
  time.sleep(delay)

if __name__=='__main__':main()
