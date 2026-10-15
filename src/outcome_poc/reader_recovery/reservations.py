"""Metadata-only duplicate closure, including all unexecuted reservations."""
import hashlib
import json
from pathlib import Path
from ..followup.study import normalized
from ..storage import content_hash


def preparation_reservations(source_root,protocol_id):
    """Fail closed on missing private metadata; completed IDs cannot be replayed.

    This catalog is publication-safe hashes/counts/paths. Its actual cohort
    files remain private. Future protocols must carry these exclusions forward.
    """
    def parse(raw):
        def unique(pairs):
            value={}
            for k,v in pairs:
                if k in value:raise ValueError('duplicate reservation metadata key')
                value[k]=v
            return value
        return json.loads(raw,object_pairs_hook=unique)
    try:
        path=Path(source_root)/'experiments/reservation-manifests.json'
        raw=path.read_bytes();catalog=parse(raw)
        if catalog['format_version']!=1 or type(catalog['protocols']) is not list:
            raise ValueError('unsupported reservation catalog')
        names=[r['protocol_id'] for r in catalog['protocols']]
        if len(names)!=len(set(names)):raise ValueError('conflicting reservation protocol identities')
        if any(r['protocol_id']==protocol_id and r['status']=='complete' for r in catalog['protocols']):
            raise ValueError('completed protocol cannot prepare another assignment; use a separately registered new protocol')
        identities={str(path):{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}
        reserved=set()
        for record in catalog['protocols']:
            cohort_path=Path(record['cohorts_path']);blob=cohort_path.read_bytes()
            actual={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)}
            if actual!=record['cohorts_identity']:raise ValueError('reservation manifest identity changed')
            cohort=parse(blob);members=[]
            for name,count in record['groups'].items():
                ids=cohort[name]
                if type(count) is not int or count<=0 or type(ids) is not list or len(ids)!=count or any(type(i) is not str or not i for i in ids):
                    raise ValueError('malformed reservation group')
                members.extend(ids)
            if len(members)!=len(set(members)):raise ValueError('overlapping reservation groups')
            reserved.update(members);identities[str(cohort_path)]=actual
        return {'reserved_ids':reserved,'identities':identities}
    except (OSError,KeyError,TypeError,ValueError) as error:
        raise ValueError(f'reservation preparation blocked: {error}') from error


def eligible_ids(tasks, membership, reserved):
    by_id = {t['task_id']:t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError('duplicate prepared task ID')
    excluded = set(reserved) | {i for i,t in by_id.items() if t['split'] != 'fit_extension'}
    excluded |= {i for g in membership if g['source'] == 'dev' for i in g['member_ids']}
    hashes = {content_hash(normalized(by_id[i]['question'])) for i in excluded if i in by_id}
    while True:
        groups = [g for g in membership if excluded.intersection(g['member_ids']) or g['group_key_hash'] in hashes]
        expanded = excluded | {i for g in groups for i in g['member_ids']}
        expanded_hashes = hashes | {g['group_key_hash'] for g in groups}
        expanded_hashes |= {content_hash(normalized(by_id[i]['question'])) for i in expanded if i in by_id}
        if expanded == excluded and expanded_hashes == hashes:
            break
        excluded,hashes = expanded,expanded_hashes
    representatives = {}
    for group in membership:
        if group['disposition'] == 'retained':
            i = group['representative_id']
            if i in representatives:
                raise ValueError('duplicate retained representative')
            representatives[i] = group
    eligible = []
    for i,task in by_id.items():
        group = representatives.get(i)
        if (group is None or not group['member_ids'] or i != min(group['member_ids']) or
                group['source'] != ('dev' if task['split']=='protected' else 'train') or
                group['group_key_hash'] != content_hash(normalized(task['question']))):
            raise ValueError('prepared representative/duplicate membership mismatch')
        if i not in excluded and group['group_key_hash'] not in hashes:
            eligible.append(i)
    if len({representatives[i]['group_key_hash'] for i in eligible}) != len(eligible):
        raise ValueError('duplicate eligible question group')
    return sorted(eligible)
