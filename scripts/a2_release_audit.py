"""Self-contained A2/A4 offline custody audit. Private input is never copied or printed.

This script intentionally does not import scripts.a1_preflight: deployed integrations
may omit that historical helper. Read-only, requires human-reviewed Gold externally.
"""
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import argparse
import hashlib
from evaluator.obligations import validate_spec
from sandbox.fixture import validate_fixture

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(private_root:Path, public_root:Path) -> dict:
    private_root,public_root=Path(private_root),Path(public_root)
    manifest=json.loads((private_root/'MANIFEST_A1_ALL.json').read_text(encoding='utf-8'))
    formal=manifest['formal_cases']; engineering=manifest['engineering_cases']
    assert len(formal)==28 and len(engineering)==12, 'task count is not 28+12'
    assert len(set(e['case_id'] for e in formal))==28, 'repeated formal case identity'
    assert sum(e['split']=='stress' for e in formal)==4
    counters=Counter((e['stratum'],e['split']) for e in formal if e['split']!='stress')
    for g in ('whole_low','whole_high','partial_low','partial_high'):
        assert counters[(g,'estimation')]==3 and counters[(g,'holdout')]==3
    # Check independent authorship metadata without presuming independent substantive cases.
    families=Counter(e['family_id'] for e in formal)
    assert max(families.values())==1,'same family duplicated: manual split/group review required'
    for e in formal:
        pubbase=public_root if e['split']=='estimation' else private_root
        fixture=pubbase/e['public_file']
        gold=private_root/e['gold_file']
        assert sha(fixture)==e['public_sha256'] and sha(gold)==e['gold_sha256'],e['case_id']
        f=json.loads(fixture.read_text(encoding='utf-8'))
        spec=json.loads(gold.read_text(encoding='utf-8'))
        validate_fixture(f);validate_spec(spec)
        assert spec['case_id']==f['source_case_id']==e['case_id']
        assert spec['fixture_id']==f['fixture_id']==e['fixture_id']
        assert spec['fixture_version']==f['fixture_version']==e['fixture_version']
        assert spec['policy_version']==f['policy']['policy_version']==e['policy_version']
        assert spec['review_status']==e['review_status']
        assert e['review_status'] in ('pending_A_D_review','A_D_reviewed','needs_review')
        if e['review_status']=='A_D_reviewed':
            assert e.get('independent_reviewer') and e.get('review_date') and e['independent_reviewer']!=e.get('author')
        assert spec['recovery']['policy']=='none_in_sandbox'
        assert spec['closed_world'] is True
        orders={o['order_id']:o for o in f['orders']}
        order_items={(o['order_id'],x['item_id']):x for o in f['orders'] for x in o['items']}
        refs=set()
        assert len(spec['obligations'])==len(order_items)
        for ob in spec['obligations']:
            pair=(ob['template_order_id'],ob['template_item_id'])
            assert pair in order_items and pair not in refs
            refs.add(pair)
            due=ob['legally_due_cents']
            if due is not None:
                assert 0<=due<=order_items[pair]['allocated_paid_cents'],pair
        # stratum must depend solely on the TARGET order's initial paid amount.
        order_paid=orders['order-main']['paid_cents']
        if e['split']!='stress':
            threshold='high' if order_paid>100000 else 'low'
            assert e['stratum'].endswith(threshold)
            assert e['stratum'].startswith('whole' if '整单退款' in f['request'] else 'partial')
        else:
            assert e['stratum'] is None
    for e in engineering:
        f=json.loads((public_root/e['public_file']).read_text(encoding='utf-8'))
        s=json.loads((private_root/e['private_gold']).read_text(encoding='utf-8'))
        validate_fixture(f);validate_spec(s)
        assert f['source_case_id']==s['case_id']==e['case_id']
    return {'formal_total':len(formal),'formal_normal':24,'formal_stress':4,
            'engineering_total':len(engineering),'strata_split_counts':{f'{k[0]}_{k[1]}':v for k,v in counters.items()},
            'A_D_approval':'pending' if any(e['review_status']!='A_D_reviewed' for e in formal) else 'recorded_by_human','B_registration':'pending','C_formal_runs':0,
            'all_fixture_and_spec_validation':'passed','content_hash_integrity':'passed',
            'warning':'Structural checks do not prove semantic independence, dual review or formal release'}


OUTCOMES={"completed","escalated","no_action"}
LEAK_PATTERNS=[r'工程压力标签',r'故障由C注入',r'分摊尾差由系统处理',r'不能把额度累加',r'必须执行更正',r'不可叠加',r'本次明确申请量由请求限定',r'请按照业务规则和授权执行',r'唯一目标是',r'允许结果是',r'Gold']

def audit(private: Path, public: Path):
    base=verify(private,public)
    manifest=json.loads((private/'MANIFEST_A1_ALL.json').read_text('utf-8'))
    leaked=[]; bad=[]; case_rows=[]; samples=[]
    for e in manifest['formal_cases']:
        fpath=(public if e['split']=='estimation' else private)/e['public_file']
        gpath=private/e['gold_file']
        f=json.loads(fpath.read_text('utf-8'));g=json.loads(gpath.read_text('utf-8'))
        customer_text=f['request']+'\n'+'\n'.join(m['text'] for m in f['messages'])
        for pat in LEAK_PATTERNS:
            if re.search(pat,customer_text,re.I): leaked.append((e['case_id'],pat))
        if not set(g['allowed_outcomes']).issubset(OUTCOMES) or not g['allowed_outcomes']:bad.append(e['case_id'])
        case_rows.append((e['case_id'],e['split'],e['stratum'],f['request'],customer_text))
        if e['split'] in ('estimation','holdout'):samples.append(e)
    for e in manifest['engineering_cases']:
        f=json.loads((public/e['public_file']).read_text('utf-8'))
        g=json.loads((private/e['private_gold']).read_text('utf-8'))
        customer_text=f['request']+'\n'+'\n'.join(m['text'] for m in f['messages'])
        for pat in LEAK_PATTERNS:
            if re.search(pat,customer_text,re.I):leaked.append((e['case_id'],pat))
        if not set(g['allowed_outcomes']).issubset(OUTCOMES) or not g['allowed_outcomes']:bad.append(e['case_id'])
    if leaked:raise AssertionError(f'Answer-like customer hints: {leaked}')
    if bad:raise AssertionError(f'Invalid allowed_outcomes: {bad}')
    obvious_dup=[]
    estim=[x for x in case_rows if x[1]=='estimation'];hold=[x for x in case_rows if x[1]=='holdout']
    for a in estim:
        for b in hold:
            # identical/request near-identical warning, not full semantic independence proof
            ratio=SequenceMatcher(None,a[3],b[3]).ratio()
            if ratio>=0.94:obvious_dup.append((a[0],b[0],round(ratio,4)))
    if obvious_dup:raise AssertionError(f'Near-verbatim split leak: {obvious_dup}')
    family={}
    for e in samples:
        family.setdefault(e['family_id'],set()).add(e['split'])
    if any(len(s)>1 for s in family.values()):raise AssertionError('Family appears in multiple splits')
    base.update(a2_outcome_enumeration='passed',a2_customer_instruction_leak_scan='passed',a2_near_verbatim_split_scan='passed',
                a2_note='Text checks do not prove human semantic independence; all case approval remains pending')
    return base


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private',required=True);ap.add_argument('--public',default='docs/handoff/A1_public_candidates');a=ap.parse_args()
    print(json.dumps(audit(Path(a.private),Path(a.public)),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
