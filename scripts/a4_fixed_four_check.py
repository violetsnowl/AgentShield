"""Offline four-case check; safe from accidental public disclosure of Gold."""
import argparse,hashlib,json
from pathlib import Path
from evaluator.obligations import validate_spec
from sandbox.fixture import validate_fixture

def check_four(private, public):
    private=Path(private);public=Path(public)
    manifest=json.loads((private/'A4_FIXED_FOUR_GOLD_MANIFEST.json').read_text(encoding='utf-8'))
    expected={'A1-W_L-01','A1-P_H-03','A1-P_L-05','ENG-A0-06'}
    assert {r['case_id'] for r in manifest['cases']}==expected
    out=[]
    for e in manifest['cases']:
        c=e['case_id']
        f=public/'development'/(c.lower()+'.json');g=private/e['gold_relative']
        assert hashlib.sha256(f.read_bytes()).hexdigest()==e['public_fixture_sha256'],c
        assert hashlib.sha256(g.read_bytes()).hexdigest()==e['gold_sha256'],c
        fixture=json.loads(f.read_text(encoding='utf-8'));spec=json.loads(g.read_text(encoding='utf-8'))
        validate_fixture(fixture);validate_spec(spec)
        assert spec['case_id']==fixture['source_case_id']==c
        assert spec['fixture_version']==fixture['fixture_version']==e['public_fixture_version']
        assert spec['policy_version']==fixture['policy']['policy_version']
        assert spec['review_status']=='pending_A_D_review'
        assert spec['coverage_status_input']=='needs_review'
        assert len(spec['obligations'])==sum(len(x['items']) for x in fixture['orders'])
        out.append({'case_id':c,'fixture_version':fixture['fixture_version'],'gold_structure':'PASS',
                    'approval':'pending_independent_human_review'})
    return {'count':len(out),'cases':out,'no_approval_forged':True}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--private',required=True)
    ap.add_argument('--public',default='docs/handoff/A1_public_candidates')
    ns=ap.parse_args()
    print(json.dumps(check_four(ns.private,ns.public),ensure_ascii=False,indent=2))

