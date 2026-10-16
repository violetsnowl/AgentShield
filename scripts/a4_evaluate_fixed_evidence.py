"""Evaluate an approved B EvidenceBundle privately, with explicit audit status."""
import argparse,json,hashlib
from pathlib import Path
from evaluator.verify import evaluate_evidence, claim_event
from actuarial.claims import calculate_claim

def run(evidence_path, spec_path, contract_path=None):
    evidence_path=Path(evidence_path);spec_path=Path(spec_path)
    raw=evidence_path.read_bytes()
    evidence=json.loads(raw);spec=json.loads(spec_path.read_text(encoding='utf-8'))
    result=evaluate_evidence(evidence,spec,evidence_sha256=hashlib.sha256(raw).hexdigest())
    # No interpretation of insurance liability from a mere technical transaction.
    if spec.get('review_status')!='A_D_reviewed':
        result['notes'].append('A/D human Gold signoff absent; result is exploratory only')
    claim=None
    if contract_path:
        contract=json.loads(Path(contract_path).read_text(encoding='utf-8'))
        claim=calculate_claim(claim_event(result),contract)
    return {'loss_result':result,'claim_result':claim,'formally_admissible':spec.get('review_status')=='A_D_reviewed'}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--evidence',required=True);a.add_argument('--spec',required=True)
    a.add_argument('--contract');a.add_argument('--output')
    n=a.parse_args();obj=run(n.evidence,n.spec,n.contract);payload=json.dumps(obj,ensure_ascii=False,indent=2)
    if n.output:
        out=Path(n.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(payload+'\n',encoding='utf-8')
        print('Result written to private destination:',out)
    else:
        # Explicit reporting contains amounts; no private obligation Gold is dumped by default.
        x=obj['loss_result'];print(json.dumps({'case_id':x['identity']['case_id'],
              'loss_status':x['loss_status'],'net_loss_cents':x['net_loss_cents'],
              'policy_compliance':x['policy_compliance'],'claim_status':obj['claim_result']['claim_status'] if obj['claim_result'] else 'not_calculated',
              'formally_admissible':obj['formally_admissible']},ensure_ascii=False))

