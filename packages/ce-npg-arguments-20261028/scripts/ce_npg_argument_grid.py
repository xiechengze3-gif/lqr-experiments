"""Pure-stdlib, deduplicated execution grid for the approved argument study."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ce-npg-arguments-20261028'
BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE / 'results' / NAME
RELEASE = BASE / 'releases' / NAME
OLD = BASE / 'results' / 'manuscript-three-groups-20261027'
CFG_PATH = ROOT / 'configs' / 'ce_npg_argument_revision_20261027.json'
CFG = json.loads(CFG_PATH.read_text(encoding='utf-8-sig'))


def schedule():
    c = CFG['NPG']
    return [b for b in c['regression_blocks'] for _ in range(c['stages_per_block_count'])]


def specs(system, trial):
    rows = []
    for family in CFG['A_families']:
        offset = 0 if family == 'scalar' else 12
        for n, m, rank in CFG['exact']['cells_n_m_r']:
            assert n == m
            old_ce = offset + [12,24,48,96].index(n) if rank == 2 else None
            rows.append(dict(algorithm='CE', n=n, r=rank, A_family=family,
                spectrum='exact', old_index=old_ce))
            for mode in ['dense','truncated']:
                old_npg = offset + 6 + (mode == 'truncated') if n == 12 and rank == 2 else None
                rows.append(dict(algorithm='NPG', n=n, r=rank, k=n if mode == 'dense' else rank,
                    mode=mode, A_family=family, spectrum='exact', old_index=old_npg))
        for spectrum, old_index in [('gapped',4),('smooth',5)]:
            rows.append(dict(algorithm='CE',n=16,r=16,A_family=family,
                spectrum=spectrum,old_index=offset+old_index))
            for k in CFG['approximate_core']['fixed_ranks']:
                rows.append(dict(algorithm='NPG',n=16,r=16,k=k,
                    mode='dense' if k == 16 else 'k'+str(k), A_family=family,
                    spectrum=spectrum,old_index=None))
    controls = [('gapped001',[2,16]),('gapped02',[2,16]),('flat',[2,8,16])]
    for spectrum, ks in controls:
        rows.append(dict(algorithm='CE',n=16,r=16,A_family='scalar',spectrum=spectrum,old_index=None))
        for k in ks:
            rows.append(dict(algorithm='NPG',n=16,r=16,k=k,
                mode='dense' if k == 16 else 'k'+str(k),A_family='scalar',
                spectrum=spectrum,old_index=None))
    for row in rows:
        row.update(system=system,trial=trial)
        label=row.get('mode','shared')
        row['id']=f"s{system}-t{trial}-{row['algorithm']}-{row['A_family']}-{row['spectrum']}-n{row['n']}-r{row['r']}-{label}"
        index=row.pop('old_index')
        row['reuse_id']=None if index is None else f's{system}-t{trial}-{index:02d}'
    assert len(rows)==86 and len({x['id'] for x in rows})==86
    return rows


def bundles():
    return [(s,t) for s in CFG['system_seeds'] for t in CFG['sampling_seeds']]


def all_specs():
    return [r for s,t in bundles() for r in specs(s,t)]


if __name__=='__main__':
    rows=all_specs()
    actual={a:sum(r['algorithm']==a for r in rows) for a in ['CE','NPG']}
    reuse={a:sum(r['algorithm']==a and r['reuse_id'] is not None for r in rows) for a in ['CE','NPG']}
    assert len(rows)==2064 and actual=={'CE':456,'NPG':1608}
    assert reuse=={'CE':240,'NPG':96}
    print(json.dumps(dict(total=len(rows),by_algorithm=actual,reuse=reuse,
        new=len(rows)-sum(reuse.values()),bundles=len(bundles()),
        assigned_actor_transitions=sum((12+1+b)*12 for b in schedule())),indent=2))
