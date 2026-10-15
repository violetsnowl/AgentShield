"""A2 private-custody QA. Read only; never promotes pending to approved."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from scripts.a1_preflight import verify

OUTCOMES={'completed','escalated','no_action'}
LEAK_PATTERNS=[r'工程压力标签',r'故障由C注入',r'分摊尾差由系统处理',r'不能把额度累加',r'必须执行更正',r'不可叠加',r'本次明确申请量由请求限定',r'请按照业务规则和授权执行',r'唯一目标是',r'允许结果是',r'Gold']


def audit(private:Path,public:Path):
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
