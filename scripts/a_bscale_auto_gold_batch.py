"""Generate *private* deterministic Gold for C's already selected B-SCALE task IDs.

No new sampling, model calls, re-verification, or public Git writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from scripts.a_bscale_auto_gold import GoldInputError, generate, source_hash
from sandbox.bscale_authorization import load_dynamic_fixture, fixture_id_for


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source-db',type=Path,required=True)
    p.add_argument('--request-ids-file',type=Path,required=True,
                   help='JSON list or B batch manifest with selected_request_ids, not Agent results')
    p.add_argument('--out-private-dir',type=Path,required=True)
    a=p.parse_args(argv)
    raw=json.loads(a.request_ids_file.read_text(encoding='utf-8'))
    request_ids=raw if isinstance(raw,list) else raw.get('selected_request_ids')
    if not isinstance(request_ids,list) or not request_ids or len(request_ids)>10:
        raise GoldInputError('expected 1-10 already sampled request IDs')
    if len(set(request_ids)) != len(request_ids):
        raise GoldInputError('duplicate selected request IDs')
    dest=a.out_private_dir.resolve()
    if 'git_ready' in dest.parts or any((x/'.git').exists() for x in (dest,*dest.parents)):
        raise GoldInputError('private output must be outside Git working tree')
    outputs=[]
    # Complete generation in memory before creating any private files.
    for rid in request_ids:
        fid=fixture_id_for(rid)
        fixture,digest=load_dynamic_fixture(fid,a.source_db)
        if digest!=source_hash(fixture):
            raise GoldInputError('fixture changed during generation')
        spec,audit=generate(fixture)
        outputs.append((rid,spec,audit))
    dest.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for rid,spec,audit in outputs:
        name=f'obligation_{rid}.json'
        data=(json.dumps(spec,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        (dest/name).write_bytes(data)
        manifest.append({'request_id':rid,'fixture_id':spec['fixture_id'],'case_id':spec['case_id'],
                         'spec_file':name,'spec_sha256':hashlib.sha256(data).hexdigest(),
                         'total_legally_due_cents':audit['total_legally_due_cents'],
                         'outcome':audit['allowed_outcomes'],'coverage_status':'needs_review',
                         'review_status':spec['review_status']})
    (dest/'PRIVATE_manifest.json').write_text(json.dumps({'scope':'private_A_to_C_after_execution_only',
        'cases':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'count':len(outputs),'private_directory':str(dest),'statuses':[x[2]['status'] for x in outputs]},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
