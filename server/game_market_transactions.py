"""Pure purchase payment-allocation rules (planning only, no mutation).

`Game.buy_cards` is the actual transaction that mutates player resources and
turn_log after allocation succeeds — it stays in `game.py`, out of scope
here. These functions only compute what a purchase *would* cost/whether it's
affordable, given already-resolved inputs (resources, ability-derived
policy, catalog costs) — no `Game`/`player` coupling.
"""


def purchase_payment_policy(has_ability):
    """Resolve which flexible-payment ability (if any) applies.

    `has_ability` is a callable `has_ability(name) -> bool`, so this stays
    decoupled from how ability lookup actually works on a `Game`/`player`.
    """
    ability_name = next(
        (name for name in ("華文傳媒", "國際線") if has_ability(name)),
        None,
    )
    return {
        'type': 'propaganda_then_money_shortfall',
        'active': ability_name is not None,
        'ability_name': ability_name,
        'eligible_cost': 'propaganda',
        'allocation_scope': 'batch',
    }


def allocate_purchase_payments(player_resources, policy, cards, effective_costs):
    """Allocate one shared resource pool across a purchase, without mutation.

    Printed/effective money costs are reserved first. For eligible propaganda
    cards, remaining propaganda is then consumed in selection order and money
    pays only the shortfall. This keeps mixed costs intact and prevents each
    card in a batch from independently reusing the same propaganda.
    """
    cards = list(cards or [])
    effective_costs = list(effective_costs or [])
    if len(cards) != len(effective_costs):
        raise ValueError('cards and effective_costs must have equal length')

    eligible = [
        bool(policy['active'] and int((cost or {}).get(policy['eligible_cost'], 0) or 0) > 0)
        for cost in effective_costs
    ]
    payments = []
    for cost, can_substitute in zip(effective_costs, eligible):
        payments.append({
            'money': int((cost or {}).get('money', 0) or 0),
            'propaganda': 0 if can_substitute else int((cost or {}).get('propaganda', 0) or 0),
        })

    fixed_propaganda = sum(payment['propaganda'] for payment in payments)
    remaining_propaganda = max(0, int(player_resources.get('propaganda', 0) or 0) - fixed_propaganda)
    substitution_money = [0 for _ in cards]

    for index, (cost, can_substitute) in enumerate(zip(effective_costs, eligible)):
        if not can_substitute:
            continue
        propaganda_cost = int((cost or {}).get('propaganda', 0) or 0)
        propaganda_payment = min(remaining_propaganda, propaganda_cost)
        money_shortfall = propaganda_cost - propaganda_payment
        payments[index]['propaganda'] = propaganda_payment
        payments[index]['money'] += money_shortfall
        substitution_money[index] = money_shortfall
        remaining_propaganda -= propaganda_payment

    payment_total = {
        'money': sum(payment['money'] for payment in payments),
        'propaganda': sum(payment['propaganda'] for payment in payments),
    }
    success = (
        int(player_resources.get('money', 0) or 0) >= payment_total['money']
        and int(player_resources.get('propaganda', 0) or 0) >= payment_total['propaganda']
    )
    return {
        'success': success,
        'payment': payment_total,
        'payments': payments,
        'substitution_money': substitution_money,
        'policy': policy,
    }
