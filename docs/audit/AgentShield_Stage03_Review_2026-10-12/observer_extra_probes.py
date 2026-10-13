"""Independent stage03 checks. Runs only isolated test DB + local/mock transports."""
import argparse,json,secrets,tempfile,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
sys.path.insert(0,str(Path(args.project).resolve()))
import httpx
from fastapi.testclient import TestClient
from api.app import create_app
from workbench.app import create_observer
results=[]
def record(name,fn):
 try: details=fn();results.append({'name':name,'pass':True,'details':details})
 except Exception as e: results.append({'name':name,'pass':False,'error':type(e).__name__+': '+str(e)})
with tempfile.TemporaryDirectory(prefix='independent-observer-') as folder:
 token=secrets.token_urlsafe(32);grant=secrets.token_urlsafe(32)
 app=create_app(Path(folder)/'isolated.sqlite3',token)
 with TestClient(app) as b:
  admin={'Authorization':'Bearer '+token}
  own=b.post('/api/v1/sessions',json={'tenant_id':'workbench-development'},headers=admin).json();sid=own['session']['session_id']
  other=b.post('/api/v1/sessions',json={'tenant_id':'outside-scope'},headers=admin).json()
  def forward(req):
   response=b.request(req.method,str(req.url),headers=dict(req.headers),content=req.content)
   return httpx.Response(response.status_code,content=response.content)
  observer=create_observer('http://127.0.0.1:8999',token,grant,transport=httpx.MockTransport(forward),frontend_dir=Path(folder)/'none')
  head={'Origin':'http://127.0.0.1:8810','X-Workbench-Request':'1','Sec-Fetch-Site':'same-origin'}
  with TestClient(observer,base_url='http://127.0.0.1:8810',raise_server_exceptions=False) as c:
   assert c.post('/observer/pair',headers=head,json={'grant':grant}).status_code==200
   def tenant_query():
    r=c.get('/observer/api/sessions?tenant_id=outside-scope',headers=head)
    assert r.status_code==200
    assert all(s['tenant_id']=='workbench-development' for s in r.json()['sessions'])
    return {'status':r.status_code,'all_fixed_tenant':True}
   record('fixed_tenant_cannot_be_overridden_by_query',tenant_query)
   def forbidden_writes():
    before=app.state.store.evidence(sid)
    paths=[f'/observer/api/sessions/{sid}/tools/submit_refund',f'/api/v1/sessions/{sid}/tools/submit_refund','/observer/api/quotes','/observer/api/admin/fixtures']
    statuses=[c.post(p,json={},headers=head).status_code for p in paths]
    assert all(s in (404,405) for s in statuses)
    after=app.state.store.evidence(sid)
    assert all(before[k]==after[k] for k in ('refunds','ledger','events','final_snapshot'))
    return {'statuses':statuses,'facts_unchanged':True}
   record('no_tool_quote_or_generic_admin_proxy',forbidden_writes)
   def cross_site():
    before=app.state.store.list_sessions('workbench-development',0,100)
    statuses=[]
    for extra in [{'Origin':'https://example.invalid'},{'Host':'example.invalid'},{'Sec-Fetch-Site':'cross-site'},{'X-Workbench-Request':'0'}]:
     r=c.post('/observer/api/sessions',json={'fixture_id':'dev-refund-v1'},headers=head|extra);statuses.append(r.status_code)
    assert statuses==[403]*4
    assert app.state.store.list_sessions('workbench-development',0,100)==before
    return {'statuses':statuses,'no_session_created':True}
   record('forbidden_browser_sources_cannot_create',cross_site)
   def readonly_boundary():
    before=app.state.store.evidence(sid);seen=[]
    for suffix in ('evidence','events','ledger'):
     r=c.get(f'/observer/api/sessions/{sid}/{suffix}',headers=head);assert r.status_code==200
     assert token not in r.text and own['session_token'] not in r.text
     assert r.headers['cache-control']=='no-store'
     assert "unsafe-eval" not in r.headers['content-security-policy']
     seen.append(suffix)
    after=app.state.store.evidence(sid)
    assert all(before[k]==after[k] for k in ('events','refunds','ledger','final_snapshot'))
    return {'resources':seen,'no_B_credential_leak':True,'facts_unchanged':True}
   record('readonly_paths_keep_headers_and_funds',readonly_boundary)
   def outside_tenant():
    statuses=[c.get(f"/observer/api/sessions/{other['session']['session_id']}/{suffix}",headers=head).status_code for suffix in ('evidence','events','ledger')]
    assert statuses==[404]*3
    return {'statuses':statuses}
   record('cross_tenant_evidence_events_ledger_denied',outside_tenant)
   def logout():
    # Retain the old cookie in this audit harness to test server-side revocation.
    saved=c.cookies.get('agentshield_observer')
    assert c.post('/observer/logout',headers=head).status_code==200
    r=c.get('/observer/api/fixtures',headers=head|{'Cookie':'agentshield_observer='+saved})
    assert r.status_code==401
    assert c.post('/observer/pair',headers=head,json={'grant':grant}).status_code==401
    return {'revoked_cookie_status':r.status_code,'grant_reusable':False}
   record('logout_revokes_cookie_server_side',logout)
Path(args.output).write_text(json.dumps({'checks':results,'passed':sum(r['pass'] for r in results),'count':len(results),'model_calls':0,'real_payments':0},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,indent=2));sys.exit(0 if all(r['pass'] for r in results) else 1)
