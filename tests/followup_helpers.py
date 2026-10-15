"""Authored fixtures through the same follow-up job/index/scoring engine."""
from dataclasses import asdict
from pathlib import Path
from outcome_poc.storage import canonical_bytes, content_hash
from outcome_poc.schemas import ReaderResult
from outcome_poc.followup.study import publish, make_schedule, identity, build_new_index
from outcome_poc.followup.clock import boot_identity, clock_identity
from retrieval_helpers import Encoder


class Tokenizer:
    chat_template='authored fixture'
    def apply_chat_template(self,messages,**kwargs):return canonical_bytes(messages).decode()


class Backend:
    tokenizer=Tokenizer()
    lifecycle=[]
    last_resources={}
    peak_mlx_bytes=None
    def __init__(self,interrupt=False):self.interrupt=interrupt;self.calls=0
    def synchronize(self):pass
    def generate(self,*args,**kwargs):
        self.calls+=1
        self.progress_callback('partial authored output',[1,2],[3])
        if self.interrupt:raise KeyboardInterrupt()
        return ReaderResult('{"answer":"violet","citations":[{"doc_id":"D0","sentence_index":0}]}',
                            None,[],'ok',2,1,[1,2],[3],'stop')
    def close(self):pass


def root_fixture(tmp_path,documents):
    root=tmp_path/'study';root.mkdir()
    tasks=[dict(task_id=f'authored-{i}',split='fit_extension',question=f'Invented lantern {i}?',
                candidate_ids=[d.doc_id for d in documents]) for i in range(3)]
    cohorts={'calibration':[tasks[0]['task_id']],'calibration_reserved':[tasks[0]['task_id']],
             'diagnosis':[tasks[1]['task_id']],'headroom':[tasks[2]['task_id']]}
    schedule=make_schedule(cohorts)
    (root/'tasks.jsonl').write_bytes(b''.join(canonical_bytes(t)+b'\n' for t in tasks))
    (root/'documents.jsonl').write_bytes(b''.join(canonical_bytes(asdict(d))+b'\n' for d in documents))
    (root/'support-doc-ids.jsonl').write_bytes(canonical_bytes({'task_id':tasks[1]['task_id'],'support_doc_ids':[documents[0].doc_id]})+b'\n')
    publish(root/'cohorts.json',cohorts);publish(root/'schedule.json',schedule)
    publish(root/'assets.json',{'assets':{'reader':{'revision':'fixture','snapshot_hash':'fixture','local_path':str(tmp_path)},
        'encoder':{'revision':'fixture','snapshot_hash':'fixture','local_path':str(tmp_path)}}})
    gold_path=tmp_path/'fixture-gold.jsonl'
    gold_path.write_bytes(b''.join(canonical_bytes({'task_id':t['task_id'],'answer':'violet',
        'supporting_facts':[[documents[0].title,0]]})+b'\n' for t in tasks))
    freeze={'settings':{'reader':{'max_context_tokens':8192,'max_new_tokens':256,'timeout_seconds':120}},
        'cohorts_hash':content_hash(cohorts),'schedule_hash':content_hash(schedule),'boot_id':boot_identity(),
        'clock':clock_identity(),'source_files':{},'privileged_inputs':{}}
    plan={'freeze':freeze,'files':{str(p.relative_to(root)):identity(p) for p in root.iterdir()},
          'gold_input':{'path':str(gold_path),'identity':identity(gold_path)}}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan)
    setup=root/'index-setup';setup.mkdir();build_new_index(setup,documents,Encoder())
    return root,plan
