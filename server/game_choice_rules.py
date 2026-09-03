"""Pure pending_choice classification (reads a choice dict only, no Game
mutation or state access).
"""


def choice_is_card_map_interaction(choice):
    if not isinstance(choice, dict):
        return False
    if choice.get('choice_key') == 'card_build_organization':
        return True
    context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
    effect_type = context.get('effect_type')
    return bool(
        choice.get('choice_key') == 'intel_network_dissolve_target'
        or (
            choice.get('choice_key') == 'support_interaction'
            and choice.get('step') == 'town'
            and effect_type in {
                'interactive_build_anywhere_inner',
                'interactive_build_near_inner',
            }
        )
        or (
            choice.get('choice_key') in {'support_interaction', 'card_dissolve_interaction'}
            and choice.get('step') == 'target'
            and effect_type in {
                'interactive_dissolve_many_near',
                'interactive_dissolve_and_build',
                'interactive_dissolve_self_and_enemy',
            }
        )
    )
