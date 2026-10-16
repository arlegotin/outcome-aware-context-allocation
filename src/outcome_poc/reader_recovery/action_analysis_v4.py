"""NEW privileged empirical screen; optimistic witnesses never confer a claim."""
from ..oracle import headroom,two_endpoint_frontier
from .action_study_v4 import SCREEN


def action_value_screen(rows,arms,screen):
    if screen!=SCREEN:raise ValueError('prospective action-value research screen changed')
    ten=arms['10'];n=len(rows)
    eligible={a:p for a,p in arms.items() if p['strict_successes']>=ten['strict_successes'] and
              p['answer_successes']>=ten['answer_successes'] and p['R'] is not None}
    best=min(eligible,key=lambda a:(eligible[a]['R'],eligible[a]['mean_T'],int(a))) if eligible else None
    anchor=eligible[best] if best else ten
    S=max(anchor['strict_successes'],ten['strict_successes']);E=max(anchor['answer_successes'],ten['answer_successes'])
    fixed_ten=two_endpoint_frontier(rows,minimum_strict_successes=ten['strict_successes'],minimum_answer_successes=ten['answer_successes'])
    common=two_endpoint_frontier(rows,minimum_strict_successes=S,minimum_answer_successes=E)
    overhead=screen['planning_routing_seconds'];qualified=[]
    for p in common['frontier']:
        if p['S']<S or p['E']<E or p['S']==0 or best is None:continue
        adjusted_R=(p['total_T']+n*overhead)/p['S']
        saving_R=1-adjusted_R/anchor['R'];saving_T=anchor['mean_T']-p['total_T']/n-overhead
        if saving_R>=screen['minimum_R_fraction_saving'] and saving_T>=screen['minimum_mean_T_saving_seconds']:
            qualified.append({**p,'R_with_planning_overhead':adjusted_R,
                'R_fraction_saving_with_planning_overhead':saving_R,'mean_T_saving_with_planning_overhead':saving_T})
    witness=min(qualified,key=lambda p:(p['R_with_planning_overhead'],p['total_T'])) if qualified else None
    diagnostic=headroom(rows);discordance=diagnostic['discordance']
    enough=discordance>=screen['minimum_strict_discordances']
    return {'continue_to_learning':bool(witness and enough),'optimistic_routing_value':bool(witness),
            'screen_witness':witness,'strict_discordance':discordance,'sufficient_discordance_for_research':enough,
            'best_eligible_fixed':best,'common_strict_anchor':S,'common_answer_anchor':E,
            'fixed_two_saves_with_empirical_quality_eligibility':bool('2' in eligible and ten['R'] is not None and eligible['2']['mean_T']<ten['mean_T']),
            'fixed_ten_frontier':fixed_ten,'common_anchor_frontier':common,'research_screen':screen,
            'reason':'bounded training investigation allowed' if witness and enough else
                     'insufficient optimistic routing advantage or discordance; retain simplest eligible fixed action',
            'allocation_claim':False,'operational_requirements':None,
            'scope':'privileged finite-sample optimistic diagnostic; one timing, no population or efficiency acceptance'}
