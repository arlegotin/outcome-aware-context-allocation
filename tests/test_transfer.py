"""Optional transfer metadata does not pretend an experiment executed."""
from copy import deepcopy
import pytest
from outcome_poc.schemas import Task
from test_ablations import api


def test_pooled_union_includes_entire_declared_population_not_query_slice():
    dev=[Task('dev','fit','development',['a','b'])]
    protected=[Task('p1','protected','one',['b','c']),Task('p2','protected','two',['d','e'])]
    before=deepcopy((dev,protected))
    result=api().pooled_corpus_manifest(dev,protected)
    assert result['document_ids']==['a','b','c','d','e']
    assert result['protected_population_count']==2 and result['development_task_count']==1
    assert result['query_restrictions'] is False and result['gold_associations'] is False
    assert (dev,protected)==before


def test_transfer_requires_future_capacity_and_prospective_manifest_without_calling_runtime():
    class Runtime:
        def __getattribute__(self,name): raise AssertionError('optional native access before release')
    result=api().transfer({'protocol_hash':'fixture'}, {}, [], Runtime())
    assert result['executed'] is False
    assert result['status']=='requires_separate_prospective_diagnostic'
    assert result['feasibility']=='not_assessed'


def test_pool_rejects_duplicate_population_and_development_protected_mix():
    t=Task('p','protected','q',['x'])
    with pytest.raises(ValueError): api().pooled_corpus_manifest([],[t,t])
    with pytest.raises(ValueError): api().pooled_corpus_manifest([t],[t])


def test_bounded_exhaustive_memmap_search_uses_all_windows_max_per_paragraph_and_ties(tmp_path):
    import numpy as np
    path=tmp_path/'synthetic.f32'
    vectors=np.memmap(path,dtype=np.float32,mode='w+',shape=(14,384))
    vectors[:]=0.;vectors[:,1]=1.
    # Outside-packet document wins through its second window; tied originals sort by ID.
    vectors[1]=0.;vectors[1,0]=1.
    vectors.flush()
    paragraphs=[{'doc_id':'outside-packet','title':'Outside','character_count':20,'sentence_count':1,
                 'vector_start':0,'window_count':2}]
    paragraphs += [{'doc_id':f'd{i:02d}','title':f'Title {i}','character_count':10,'sentence_count':1,
                    'vector_start':i+2,'window_count':1} for i in range(12)]
    query=np.zeros(384,dtype=np.float32);query[0]=1.
    result=api().pooled_top_ten(vectors,paragraphs,query,batch_rows=3)
    assert [r.doc_id for r in result['ranking']]==['outside-packet',*['d%02d'%i for i in range(9)]]
    assert result['window_count']==14 and result['document_count']==13
    assert result['maximum_batch_rows']==3 and result['batches']==5
    assert result['ranking'][0].score==1. and result['packet_restrictions_used'] is False
    assert result['full_seconds']>=result['dots_seconds']>=0.


def test_pooled_search_rejects_uncovered_vectors_and_nonfloat32(tmp_path):
    import numpy as np
    meta=[{'doc_id':'d','title':'D','character_count':1,'sentence_count':1,'vector_start':0,'window_count':1}]
    query=np.zeros(384,dtype=np.float32);query[0]=1.
    with pytest.raises(ValueError): api().pooled_top_ten(np.zeros((2,384),dtype=np.float32),meta,query)
    with pytest.raises(ValueError): api().pooled_top_ten(np.zeros((1,384),dtype=np.float64),meta,query)
