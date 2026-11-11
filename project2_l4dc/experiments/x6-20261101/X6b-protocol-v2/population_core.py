from scipy.linalg import solve_discrete_lyapunov
import frozen_engine as e
import estimation

def population(config):
    rows=[]
    for n in config['n_values']:
        for system in [9101,9102]:
            s=estimation.model('S',n,system)
            for algorithm,grid in [('NPG',config['population_NPG_T_grid']),('PI',config['population_PI_T_grid'])]:
                k=s['K0'].copy();dead=False
                for stage in range(1,max(grid)+1):
                    if not dead:
                        f=s['A']-s['B']@k
                        p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                        g=s['B'].T@p@s['B'];z=-s['B'].T@p@f
                        k=e.actor_learner(k,s['R'],g,z,'dense',2,algorithm,config['eta'])
                        assessment=e.assess(s,k);dead=not assessment['stable']
                    if stage in grid:
                        rows.append(dict(n=n,system=system,algorithm=algorithm,T=stage,
                            stable=not dead,relative_gap=assessment['relative_gap'] if not dead else None))
    selected={}
    for algorithm,grid in [('NPG',config['population_NPG_T_grid']),('PI',config['population_PI_T_grid'])]:
        qualifying=[]
        for T in grid:
            subset=[r for r in rows if r['algorithm']==algorithm and r['T']==T]
            assert len(subset)==8
            if all(r['stable'] and r['relative_gap']<=.05 for r in subset):qualifying.append(T)
        selected[algorithm]=qualifying[0] if qualifying else None
    return dict(rows=rows,selected_T=selected,simulated_transitions=0,
                pilot_systems_only=True,formal_learning_outputs_used=False)


