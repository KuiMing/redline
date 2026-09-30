"""Mixin holding the play_card / pending-choice-resolution / reaction-stack /
support-interaction system for :class:`server.game.Game`.

This is the *stateful* dispatch core of card play: it reads and writes
``self.turn_log``, ``self.pending_choice``, player hand/resources/organizations,
and calls ``self.log(...)``, so unlike the earlier pure-function extractions in
``server/game_*_rules.py``, these methods could not be rewritten as standalone
functions without inventing a new state-passing architecture. Instead they are
moved here verbatim as a mixin class purely to shrink ``game.py`` -- this is a
verbatim text relocation, not a rewrite; nothing about the logic changed.
"""

import random

from server.cards import Card
from server.game_models import TurnPhase

# Pending choices that may be cancelled by closing the modal without any side effect.
# These are voluntary Red Army activated abilities whose ability-use count is only consumed
# when the choice is RESOLVED (not when it is opened), so cancelling restores the exact
# pre-activation state. Every other pending choice is either a mandatory settlement/penalty,
# a mid-card-effect step where the card is already spent, or a map-context choice — those
# must be resolved (or, for map choices, are dismissed through the map), so they are NOT here.
#
# Moved here (from game.py) alongside cancel_pending_choice(), which is its only consumer in
# this module; game.py's state() projection also reads it, so it is re-exported there via
# `from server.game_card_play import CANCELLABLE_CHOICE_KEYS`.
CANCELLABLE_CHOICE_KEYS = frozenset({
    'red_army_ccdi_discard_draw',              # 中紀委
    'red_army_propaganda_department_target',   # 政工部
    'red_army_state_security_target',          # 國安部
})

# `context['effect_type']` values that represent a *player-initiated* dissolve-organization
# target pick (as opposed to a build/discard interaction that happens to share the same
# `card_dissolve_interaction` / `support_interaction` choice_key plumbing). Used both to decide
# which pending choices the cancellable-dissolve-target feature applies to, and to gate the
# "defer every board mutation to the final confirmation" behaviour in
# `_resolve_support_interaction_result` (see `_dissolve_cancel_kwargs` below).
DISSOLVE_INTERACTIVE_EFFECT_TYPES = frozenset({
    'interactive_dissolve_many_near',       # 內應間諜；北國奧援 II/III；臺灣奧援 II
    'interactive_dissolve_self_and_enemy',  # 派遣間諜；北國奧援 I
    'interactive_dissolve_and_build',       # 臺灣奧援 III
})


class CardPlayMixin:
    def _set_pending_card_choice(self, player, choice_key, cards, prompt, **extra):
        card_list = list(cards)
        card_zones = extra.pop('card_zones', None)
        if card_zones:
            normalized_cards = []
            for card, zone in zip(card_list, card_zones):
                normalized_cards.append({
                    'card': card,
                    'zone': zone.get('zone') if isinstance(zone, dict) else None,
                    'zone_label': zone.get('zone_label') if isinstance(zone, dict) else None,
                })
            card_list = normalized_cards
        self.pending_choice = {
            'type': 'card_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'cards': card_list,
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_multi_card_choice(self, player, choice_key, cards, prompt, count, **extra):
        self.pending_choice = {
            'type': 'multi_card_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'cards': list(cards),
            'prompt': prompt,
            'count': count,
            **extra,
        }
        return {'pending_choice': True}

    def _set_pending_option_choice(self, player, choice_key, options, prompt, **extra):
        self.pending_choice = {
            'type': 'option_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'options': list(options),
            'prompt': prompt,
            **extra,
        }
        return {'pending_choice': True}

    def _build_choice_entitlement_count(self, choice):
        if not isinstance(choice, dict):
            return 0
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        if choice.get('choice_key') == 'support_interaction':
            return 1 if context.get('effect_type') in {
                'interactive_build_anywhere_inner',
                'interactive_build_near_inner',
                'interactive_dissolve_and_build',
            } else 0
        if choice.get('choice_key') != 'card_build_organization':
            return 0
        later_builds = sum(
            1
            for effect in (context.get('remaining_effects') or [])
            if isinstance(effect, dict) and effect.get('type') == 'build'
        )
        return 1 + later_builds

    def _refresh_card_build_choice_projection(self):
        choice = self.pending_choice
        if not isinstance(choice, dict) or choice.get('choice_key') != 'card_build_organization':
            return 0
        remaining = self._remaining_card_build_entitlements()
        source_name = choice.get('source_name') or '建立組織卡'
        choice['remaining_builds'] = remaining
        choice['prompt'] = f"{source_name}：選擇要建立組織的城鎮（尚可建立 {remaining} 個）。"
        return remaining

    def _refresh_queued_card_map_choice(self, player, choice):
        if choice.get('choice_key') == 'card_build_organization':
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            towns = self._card_build_town_choices(player, context.get('effect') or {})
            if not towns:
                return False
            choice['towns'] = list(towns)
            return True
        if choice.get('choice_key') == 'intel_network_dissolve_target':
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            targets = self._interactive_support_dissolve_targets(
                player,
                require_self_sacrifice=False,
                max_steps=int(context.get('range_limit', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                target_region=context.get('target_region'),
                include_shared_source=True,
            )
            if not targets:
                return False
            choice['targets'] = list(targets)
            return True
        if self._choice_is_card_map_interaction(choice):
            self.pending_choice = None
            if not self._refresh_support_flow_choice_after_stale_result(player, choice):
                return False
            refreshed = self.pending_choice
            if not isinstance(refreshed, dict):
                return False
            choice.clear()
            choice.update(refreshed)
            self.pending_choice = None
            return True
        return False

    def _settle_deferred_card_play_triggers(self, fallback_player, choice):
        # Whether a deferred post_play_faction_triggers marker should fire now is decided
        # PURELY by an explicit `is_final_confirmation` flag set on the choice dict itself, by
        # the resolver code path that just committed real board state for it (see
        # `_resolve_support_interaction_result`'s dissolve/atomic-multi-target commits,
        # `_resolve_target_choice`'s intel_network_dissolve_target commit,
        # `_resolve_support_flow_choice`'s "effect fizzled" branch, and the `choose_one`
        # option-A/C-or-no-legal-target branch). This is deliberately NOT inferred by searching
        # for whether the marker is still reachable from `self.pending_choice` (or any nested
        # `flow_context`): a flow's paused continuation can legitimately live in several other
        # places instead -- `self._queued_card_build_choices`, `self._deferred_build_choice`, or
        # simply nowhere yet if `_set_pending_option_choice` (used by 情報網's `choose_one`)
        # never engages the queue at all -- and interleaving a second card's play in between a
        # flow's stages (ordinary, frequently-tested game machinery) can make any one of those
        # locations hold the "wrong" choice at the moment this runs. Checking a flag on the
        # choice actually being resolved right now is immune to all of that by construction.
        if not isinstance(choice, dict) or not choice.get('is_final_confirmation'):
            return False
        context = choice.get('context')
        if not isinstance(context, dict):
            return False
        deferred_triggers = context.pop('post_play_faction_triggers', None)
        if not isinstance(deferred_triggers, dict):
            return False

        trigger_player = next(
            (candidate for candidate in self.players if candidate.id == deferred_triggers.get('player_id')),
            fallback_player,
        )
        self._apply_card_play_faction_abilities(
            trigger_player,
            cost_has_money=bool(deferred_triggers.get('cost_has_money')),
            cost_has_propaganda=bool(deferred_triggers.get('cost_has_propaganda')),
            played_card=deferred_triggers.get('played_card'),
            used_faction_ability_names=deferred_triggers.get('used_faction_ability_names'),
        )
        return True

    def _queue_new_card_map_choice_behind_deferred(self, player, new_choice):
        deferred = self._deferred_build_choice
        if not (
            isinstance(deferred, dict)
            and deferred.get('player_id') == player.id
            and self._choice_is_card_map_interaction(new_choice)
        ):
            return None
        self._queued_card_build_choices.append(new_choice)
        self.pending_choice = deferred
        self._deferred_build_choice = None
        remaining = self._refresh_card_build_choice_projection()
        response = {'pending_choice': True, 'queued_map_choice': True}
        if remaining:
            response['remaining_builds'] = remaining
        return response

    def _set_pending_town_choice(self, player, choice_key, towns, prompt, **extra):
        normalized = []
        for town in list(towns or []):
            if isinstance(town, dict):
                item = dict(town)
            else:
                item = {'town': town}
            if item.get('town'):
                normalized.append(item)
        new_choice = {
            'type': 'town_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'towns': normalized,
            'prompt': prompt,
            **extra,
        }
        queued = self._queue_new_card_map_choice_behind_deferred(player, new_choice)
        if queued:
            return queued
        self.pending_choice = new_choice
        if choice_key == 'card_build_organization':
            remaining = self._refresh_card_build_choice_projection()
            return {'pending_choice': True, 'remaining_builds': remaining}
        return {'pending_choice': True}

    def _set_pending_target_choice(self, player, choice_key, targets, prompt, **extra):
        normalized = []
        for target in list(targets or []):
            if isinstance(target, dict):
                item = dict(target)
            else:
                item = {'id': str(target), 'label': str(target)}
            if item.get('id') is not None:
                normalized.append(item)
        new_choice = {
            'type': 'target_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'targets': normalized,
            'prompt': prompt,
            **extra,
        }
        queued = self._queue_new_card_map_choice_behind_deferred(player, new_choice)
        if queued:
            return queued
        self.pending_choice = new_choice
        return {'pending_choice': True}

    def _dissolve_cancel_kwargs(self, context):
        """Given a `context` dict that may carry a `_dissolve_cancel_snapshot` (seeded once, at
        the moment a player-initiated dissolve card's *first* pending choice opens -- see
        `play_card`'s `action_context['_dissolve_cancel_snapshot']`, `_start_card_dissolve_interaction`,
        and `_commit_support_card_play`), return the `**extra` kwargs that mark a
        `_set_pending_support_flow_choice`/`_set_pending_target_choice` call as cancellable with a
        full rollback. `context` is threaded verbatim through every stage of these flows
        (`next_context = dict(context)` / `{**context, ...}`), so passing this snapshot through
        forward at every stage-transition call site is what lets `cancel_pending_choice()` fully
        unwind the play from *any* stage, not just the first.

        Returns {} (not cancellable) when no snapshot is present -- e.g. non-dissolve
        support_interaction steps (build/discard) never opt in, and forced/mandatory dissolve
        choices (event_red_dissolve, era_red_bonus_dissolve_target, intel_network's own
        `choose_one` gate aside) never seed a snapshot in the first place.
        """
        snapshot = (context or {}).get('_dissolve_cancel_snapshot')
        if not isinstance(snapshot, dict) or snapshot.get('card') is None:
            return {}
        return {
            'cancellable': True,
            'rollback_card': snapshot.get('card'),
            'rollback_hand_index': snapshot.get('hand_index'),
            # What THIS card's play itself contributed to the reference-counted turn_log
            # bookkeeping -- cancel_pending_choice() decrements exactly this, which stays correct
            # regardless of what order multiple interleaved cancellable cards get cancelled in
            # (see _note_*/_undo_* helpers and Game._new_turn_log's field comment).
            'rollback_contributed_money_cost': bool(snapshot.get('contributed_money_cost')),
            'rollback_contributed_propaganda_cost': bool(snapshot.get('contributed_propaganda_cost')),
            'rollback_contributed_nonstarter_name': snapshot.get('contributed_nonstarter_name'),
            'rollback_borrowed_owner_id': snapshot.get('borrowed_owner_id'),
            'rollback_borrowed_purchase_area_index': snapshot.get('borrowed_purchase_area_index'),
            # What THIS card's own play changed in event_progress (count/completed_player_ids),
            # captured as a delta rather than an absolute before/after pair -- see
            # _event_progress_delta/_undo_event_progress_delta below for why: an absolute
            # snapshot restore has exactly the same interleaved-cancellation-order bug the
            # turn_log fields had (fixed via reference counting) -- cancelling one of two
            # interleaved contributors would stomp the other's still-live, already-correct
            # contribution. `event_progress` itself isn't naturally a simple counter (it also
            # carries `succeeded`/`status`/`completed_player_ids`/attribution fields derived
            # from the count), so instead of a parallel ref-count structure, this undoes exactly
            # this play's own numeric contribution and re-derives the dependent fields from the
            # result, which is equivalent in effect but doesn't require threading new
            # always-present internal counters through Game._new_turn_log-style state for a
            # value (event_progress) that isn't turn-scoped the same way.
            'rollback_event_progress_delta': self._event_progress_delta(
                snapshot.get('event_progress'), snapshot.get('event_progress_after')
            ),
        }

    def _event_progress_delta(self, before, after):
        """What a single card play's own _track_event_progress call(s) changed, as a small
        delta descriptor -- or None if nothing changed (no active mission, trigger type didn't
        match, event already settled, etc.) or either snapshot isn't a dict.

        Deliberately delta-based, not an absolute before/after pair: see the long comment on
        `rollback_event_progress_delta` in `_dissolve_cancel_kwargs` for why an absolute
        snapshot restore is unsafe under interleaved cancellable plays.
        """
        if not isinstance(before, dict) or not isinstance(after, dict) or before == after:
            return None
        count_delta = int(after.get('count', 0) or 0) - int(before.get('count', 0) or 0)
        added_completed_player_ids = []
        if isinstance(after.get('completed_player_ids'), list):
            before_ids = set(before.get('completed_player_ids') or [])
            after_ids = set(after.get('completed_player_ids') or [])
            added_completed_player_ids = sorted(after_ids - before_ids)
        if not count_delta and not added_completed_player_ids:
            return None
        return {
            'count_delta': count_delta,
            'added_completed_player_ids': added_completed_player_ids,
            # Identifies THIS play's own entry in event_progress['_actor_contributions'] (see
            # Game._track_event_progress) so _undo_event_progress_delta can pop exactly that
            # entry by token -- not by value/position -- and re-derive last_actor_id/name/token
            # from whichever contribution is now the most recent SURVIVING one. Deliberately NOT
            # a before/after id VALUE comparison: two different interleaved plays by the SAME
            # player write the identical last_actor_id/name, so a bare value comparison can't
            # tell "still this play's own, uncontested, attribution" apart from "coincidentally
            # the same actor id a later, still-live play also wrote"; and deliberately NOT a
            # "restore my own before-play snapshot" either, since that snapshot can itself
            # already be stale by undo time (see the stack's own comment in
            # Game._track_event_progress for why). (Parent-level review, defect 1 follow-up.)
            'last_actor_token_after': after.get('last_actor_token'),
        }

    def _undo_event_progress_delta(self, delta):
        """Reverse exactly what one card play's `_event_progress_delta` recorded, against the
        CURRENT live `self.event_progress` -- not by overwriting it with an absolute snapshot,
        so any OTHER still-live interleaved cancellable play's own independent contribution is
        left untouched. `succeeded`/`status` are pure functions of count vs. required (mirroring
        `_track_event_progress`'s own derivation), so they're recomputed from the adjusted count
        rather than separately tracked; `event_notification` is regenerated the same way
        `_track_event_progress` itself does, from the corrected `event_progress`.
        """
        if not isinstance(delta, dict):
            return
        progress = self.event_progress
        if not isinstance(progress, dict) or progress.get('settled'):
            return
        added_ids = delta.get('added_completed_player_ids') or []
        if added_ids and isinstance(progress.get('completed_player_ids'), list):
            removed = set(added_ids)
            progress['completed_player_ids'] = [
                pid for pid in progress['completed_player_ids'] if pid not in removed
            ]
            # each_non_red_player mode derives count directly from this list's length.
            progress['count'] = len(progress['completed_player_ids'])
        else:
            count_delta = int(delta.get('count_delta', 0) or 0)
            if count_delta:
                progress['count'] = max(0, int(progress.get('count', 0) or 0) - count_delta)
        required = int(progress.get('required', 0) or 0)
        if required > 0:
            now_succeeded = int(progress.get('count', 0) or 0) >= required
            progress['succeeded'] = now_succeeded
            progress['status'] = 'success_pending' if now_succeeded else 'active'
        # Remove exactly THIS play's own entry from the ordered "still-live contributors" stack
        # (by token, not by value/position), then re-derive last_actor_id/name/token from
        # whatever is now the most recent SURVIVING contribution. NOT a "restore my own
        # before-play value" -- a value-snapshot restore is unsafe here even beyond the
        # same-actor-id ambiguity a token fixes: the "before" value captured when THIS play
        # started may itself already be a now-stale snapshot of a DIFFERENT play's contribution
        # that has since been independently cancelled (see the long comment on the stack in
        # Game._track_event_progress), which restoring it would incorrectly resurrect. Popping
        # by token and re-deriving from the live stack's new top is correct under every
        # interleaved cancellation order (parent-level review, defect 1 follow-up).
        token_after = delta.get('last_actor_token_after')
        stack = progress.get('_actor_contributions')
        if token_after and isinstance(stack, list):
            new_stack = [entry for entry in stack if entry.get('token') != token_after]
            if len(new_stack) != len(stack):
                progress['_actor_contributions'] = new_stack
                if new_stack:
                    top = new_stack[-1]
                    progress['last_actor_id'] = top.get('actor_id')
                    progress['last_actor_name'] = top.get('actor_name')
                    progress['last_actor_token'] = top.get('token')
                else:
                    progress.pop('last_actor_id', None)
                    progress.pop('last_actor_name', None)
                    progress.pop('last_actor_token', None)
                    progress.pop('_actor_contributions', None)
        self.event_notification = self._event_display_payload()

    # --- Reference-counted played_money_card/played_propaganda_card/played_nonstarter_names ---
    # bookkeeping (see the field comments in Game._new_turn_log). Every card play that
    # contributes to one of these public flags calls the matching _note_* helper; a later
    # cancel_pending_choice() call for that SAME play (if it was cancellable) calls the matching
    # _undo_* helper. This keeps the flags correct under any interleaving/cancellation order of
    # multiple cancellable plays, not just strict reverse-of-play order.
    def _note_money_cost_card_played(self):
        self.turn_log['_money_cost_card_refs'] = int(self.turn_log.get('_money_cost_card_refs', 0) or 0) + 1
        self.turn_log['played_money_card'] = True

    def _undo_money_cost_card_played(self):
        refs = max(0, int(self.turn_log.get('_money_cost_card_refs', 0) or 0) - 1)
        self.turn_log['_money_cost_card_refs'] = refs
        self.turn_log['played_money_card'] = refs > 0

    def _note_propaganda_cost_card_played(self):
        self.turn_log['_propaganda_cost_card_refs'] = int(self.turn_log.get('_propaganda_cost_card_refs', 0) or 0) + 1
        self.turn_log['played_propaganda_card'] = True

    def _undo_propaganda_cost_card_played(self):
        refs = max(0, int(self.turn_log.get('_propaganda_cost_card_refs', 0) or 0) - 1)
        self.turn_log['_propaganda_cost_card_refs'] = refs
        self.turn_log['played_propaganda_card'] = refs > 0

    def _note_nonstarter_name_played(self, card_name):
        refs = self.turn_log.setdefault('_nonstarter_name_refs', {})
        refs[card_name] = int(refs.get(card_name, 0) or 0) + 1
        self.turn_log['played_nonstarter_names'] = [name for name, count in refs.items() if count > 0]

    def _undo_nonstarter_name_played(self, card_name):
        refs = self.turn_log.setdefault('_nonstarter_name_refs', {})
        if card_name in refs:
            remaining = max(0, int(refs[card_name] or 0) - 1)
            if remaining > 0:
                refs[card_name] = remaining
            else:
                # Prune zero-count entries entirely (rather than leaving `name: 0`) so a fully
                # cancelled turn's internal bookkeeping is byte-identical to a turn where nothing
                # was ever played, not just "derives the same boolean/list."
                del refs[card_name]
        self.turn_log['played_nonstarter_names'] = [name for name, count in refs.items() if count > 0]

    def _set_pending_support_flow_choice(self, player, choice_key, step, prompt, **extra):
        new_choice = {
            'type': 'support_flow_choice',
            'choice_key': choice_key,
            'player_id': player.id,
            'step': step,
            'prompt': prompt,
            **extra,
        }
        queued = self._queue_new_card_map_choice_behind_deferred(player, new_choice)
        if queued:
            return queued
        self.pending_choice = new_choice
        return {'pending_choice': True}

    def _resolve_card_choice(self, player, choice, index, target_player_ids=None):
        cards = choice.get('cards') or []
        if index is None or index < 0 or index >= len(cards):
            return {'error': 'Invalid choice index'}
        chosen = cards[index]
        choice_key = choice.get('choice_key')

        if choice_key == 'recruit_talent':
            chosen_entry = chosen if isinstance(chosen, dict) else None
            chosen_card = chosen_entry.get('card') if chosen_entry else chosen
            source_zone = None
            if chosen_entry:
                source_zone = chosen_entry.get('zone')
            elif chosen_card in player.deck.discard_pile:
                source_zone = 'discard_pile'
            elif chosen_card in player.deck.draw_pile:
                source_zone = 'draw_pile'
            # 卡面規則只說「任選 1 張加入手牌，而後將牌庫洗牌」——沒被選中的候選牌（不論
            # 原本在牌庫還是棄牌堆）都應該原地保留，只是牌庫最後會被洗牌。先前這裡誤把
            # 「候選清單裡除了被選中那張以外的每一張」全部從牌庫／棄牌堆移除，等同直接
            # 銷毀玩家整副牌庫——這正是 playtest 回報「紅軍再次使用網羅人才時有時只顯示
            # 棄牌堆，漏掉己方牌庫」的根本原因：上一次使用就已經把牌庫清空了，不是候選
            # 投影或畫面顯示的問題（2026-08-03 稽核修正）。
            if chosen_card in player.deck.draw_pile:
                player.deck.draw_pile.remove(chosen_card)
                source_zone = source_zone or 'draw_pile'
            if chosen_card in player.deck.discard_pile:
                player.deck.discard_pile.remove(chosen_card)
                source_zone = source_zone or 'discard_pile'
            player.hand.append(chosen_card)
            import random
            random.shuffle(player.deck.draw_pile)
            self.pending_choice = None
            chosen_name = getattr(chosen_card, 'name', str(chosen_card))
            if source_zone == 'discard_pile':
                self.log(f"{player.name} recruited {chosen_name} from discard via 網羅人才")
            else:
                self.log(f"{player.name} recruited {chosen_name} from deck")
            return {'success': True, 'chosen_card': chosen_name, 'source_zone': source_zone}

        if choice_key in {'gain_any_from_discard', 'gain_from_discard'}:
            if chosen not in player.deck.discard_pile:
                return {'error': 'Chosen card not in discard pile'}
            player.deck.discard_pile.remove(chosen)
            player.hand.append(chosen)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} gained {getattr(chosen, 'name', str(chosen))} from discard via {source_name}")
            return {'success': True, 'chosen_card': getattr(chosen, 'name', str(chosen))}

        if choice_key == 'event_topdeck_from_discard':
            if chosen not in player.deck.discard_pile:
                return {'error': 'Chosen card not in discard pile'}
            player.deck.discard_pile.remove(chosen)
            player.deck.draw_pile.append(chosen)
            self.pending_choice = None
            source_name = choice.get('source_name') or (self.current_event or {}).get('name') or choice_key
            chosen_name = getattr(chosen, 'name', str(chosen))
            self.log(f"{player.name} placed {chosen_name} on deck top via {source_name}")
            return {'success': True, 'chosen_card': chosen_name}

        if choice_key == 'underground_party':
            player.hand.append(chosen)
            removed = []
            for i, card in enumerate(cards):
                if i == index:
                    continue
                returned = self._return_removed_card_to_purchase_supply(card)
                if returned is None:
                    returned = self._remove_card_from_game(card)
                removed.append(returned)
            self.pending_choice = None
            self.log(f"{player.name} chose {getattr(chosen, 'name', str(chosen))} via 地下黨")
            return {
                'success': True,
                'chosen_card': getattr(chosen, 'name', str(chosen)),
                'removed_cards': removed,
            }

        if choice_key == 'use_purchase_area_card':
            source_entry = chosen if isinstance(chosen, dict) else {'card': chosen}
            source = source_entry.get('card')
            purchase_index = source_entry.get('purchase_index')
            if source is None:
                return {'error': 'Chosen purchase-area card missing'}
            borrowed = self._copy_purchase_card(source)
            if purchase_index is not None:
                setattr(borrowed, '_return_to_purchase_area_index', purchase_index)
            player.hand.append(borrowed)
            self.pending_choice = None
            self.log(f"{player.name} borrowed {getattr(borrowed, 'name', str(borrowed))} from purchase area")
            borrowed_index = len(player.hand) - 1
            action_result = self.play_card(
                borrowed_index,
                mode='action',
                target_player_ids=target_player_ids,
            )
            if action_result.get('error'):
                return action_result
            response = {
                'success': True,
                'chosen_card': getattr(borrowed, 'name', str(borrowed)),
                'purchase_index': purchase_index,
                'zone_label': source_entry.get('zone_label') or '購買區',
            }
            if 'pending_choice' in action_result:
                response['pending_choice'] = action_result.get('pending_choice')
            return response

        if choice_key == 'trash_from_hand_or_discard':
            card = chosen.get('card') if isinstance(chosen, dict) else chosen
            zone = chosen.get('zone') if isinstance(chosen, dict) else None
            zone_label = chosen.get('zone_label') if isinstance(chosen, dict) else None
            if zone == 'hand':
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
                player.hand.remove(card)
            elif zone == 'discard':
                if card not in player.deck.discard_pile:
                    return {'error': 'Chosen card not in discard pile'}
                player.deck.discard_pile.remove(card)
            else:
                return {'error': 'Unsupported trash source'}
            if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}:
                self.turn_log['non_starter_discard'] = True
            returned = self._return_removed_card_to_purchase_supply(card)
            if returned is None:
                returned = self._remove_card_from_game(card)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {getattr(card, 'name', str(card))} from {zone_label or zone} via {source_name}")
            return {
                'success': True,
                'chosen_card': getattr(card, 'name', str(card)),
                'zone': zone,
                'zone_label': zone_label,
                'removed_card': returned,
            }

        if choice_key == 'optional_trash':
            if isinstance(chosen, dict) and chosen.get('skip'):
                # 選擇不移除：本牌照常進棄牌堆，且不觸發「若移除本牌」的後續效果
                self.pending_choice = None
                resume = self._resume_after_optional_trash(player, choice, removed_current_card=False)
                self.log(f"{player.name} declined to trash via {choice.get('source_name') or 'optional_trash'}")
                return {
                    'success': True,
                    'skipped': True,
                    **({'pending_choice': True} if isinstance(resume, dict) and resume.get('pending_choice') else {}),
                }
            card = chosen.get('card') if isinstance(chosen, dict) else chosen
            zone = chosen.get('zone') if isinstance(chosen, dict) else None
            zone_label = chosen.get('zone_label') if isinstance(chosen, dict) else None
            removes_current_card = bool(chosen.get('removes_current_card')) if isinstance(chosen, dict) else False
            if card is None:
                return {'error': 'Chosen card missing'}
            if zone == 'current_card':
                pass
            elif zone == 'hand':
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
                player.hand.remove(card)
            else:
                return {'error': 'Unsupported optional trash source'}
            if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}:
                self.turn_log['non_starter_discard'] = True
            returned = self._return_removed_card_to_purchase_supply(card)
            if returned is None:
                returned = self._remove_card_from_game(card)
            if removes_current_card:
                choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else None
                if isinstance(choice_context, dict):
                    choice_context['removed_current_card'] = True
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {getattr(card, 'name', str(card))} from {zone_label or zone} via {source_name}")
            followup = choice.get('followup_target_choice') if isinstance(choice, dict) else None
            if isinstance(followup, dict) and followup.get('targets'):
                self.pending_choice = {
                    'type': 'target_choice',
                    'choice_key': followup.get('choice_key') or 'target_choice',
                    'player_id': player.id,
                    'targets': list(followup.get('targets') or []),
                    'prompt': followup.get('prompt') or '請選擇目標。',
                    'source_name': followup.get('source_name') or source_name,
                    'context': {
                        'source_name': source_name,
                        'removed_card': returned,
                        'removed_current_card': removes_current_card,
                        'trashed_card_name': getattr(card, 'name', str(card)),
                        **(choice.get('context') if isinstance(choice.get('context'), dict) else {}),
                    },
                }
                return {
                    'success': True,
                    'chosen_card': getattr(card, 'name', str(card)),
                    'zone': zone,
                    'zone_label': zone_label,
                    'removed_card': returned,
                    'removed_current_card': removes_current_card,
                    'pending_choice': True,
                }
            self.pending_choice = None
            resume_result = self._resume_after_optional_trash(player, choice, removed_current_card=removes_current_card)
            return {
                'success': True,
                'chosen_card': getattr(card, 'name', str(card)),
                'zone': zone,
                'zone_label': zone_label,
                'removed_card': returned,
                'removed_current_card': removes_current_card,
                **({'pending_choice': True} if isinstance(resume_result, dict) and resume_result.get('pending_choice') else {}),
            }

        if choice_key in {'armed_target_discard', 'era_bonus_discard_on_red_card'}:
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            initiator = next((p for p in self.players if getattr(p, 'id', None) == choice.get('initiator_player_id')), None)
            if initiator is not None and choice.get('draw_on_success'):
                self._draw_player_cards(initiator, int(choice.get('draw_on_success')))
            initiator_name = choice.get('initiator_player_name') or '其他玩家'
            target_name = choice.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_key
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            if choice_key == 'era_bonus_discard_on_red_card':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_discard_on_red_card',
                    'status': 'resolved',
                    'discarded_count': 1,
                    'target_player_id': getattr(player, 'id', None),
                })
            response = {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }
            followup = self._start_era_followup_target_choice(choice.get('era_followup_target_choice'))
            if followup and followup.get('pending_choice'):
                response['pending_choice'] = True
            return response

        if choice_key == 'org_exp_repeat_discard':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            ctx = dict(choice.get('context') or {})
            source_name = choice.get('source_name') or ctx.get('card_name') or '組織經驗甲'
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.pending_choice = None
            self.log(f"{player.name} 棄掉{getattr(chosen, 'name', str(chosen))}以透過{source_name}重複建立組織")
            towns = self._card_build_town_choices(player, ctx.get('effect') or {})
            if not towns:
                self.log(f"{player.name} 透過{source_name}重複建立組織，但目前沒有合法的城鎮可以建立")
                return {'success': True, 'discarded_card': getattr(chosen, 'name', str(chosen)), 'no_build_town': True}
            self._set_pending_town_choice(
                player,
                'card_build_organization',
                towns,
                f'{source_name}：選擇要建立組織的城鎮。',
                source_name=source_name,
                context=ctx,
            )
            return {'success': True, 'discarded_card': getattr(chosen, 'name', str(chosen)), 'pending_choice': True}

        if choice_key == 'topdeck_purchased_choice':
            if chosen not in player.deck.discard_pile:
                return {'error': 'Chosen card not in discard pile'}
            player.deck.discard_pile.remove(chosen)
            player.deck.draw_pile.append(chosen)
            self.pending_choice = None
            ctx = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            source_name = choice.get('source_name') or ctx.get('card_name') or '行動預告'
            self.log(f"{player.name} placed bought card {getattr(chosen, 'name', str(chosen))} on deck top via {source_name}")
            if ctx.get('end_turn_topdeck_flow'):
                # 從回合結束的 drain 流程進來：先處理完剩餘頂牌權利，才真正結束回合
                pending = self._prompt_end_turn_topdeck_action_if_available()
                if pending and pending.get('pending_choice'):
                    return {'success': True, 'topdecked_card': getattr(chosen, 'name', str(chosen)), 'pending_choice': True}
                self._end_turn()
            return {'success': True, 'topdecked_card': getattr(chosen, 'name', str(chosen))}

        if choice_key == 'guess_ability_bottom_card':
            ctx = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            self.pending_choice = None
            return self._resolve_guess_ability_with_bottom_card(player, ctx.get('action_name'), ctx.get('guess'), chosen)

        if choice_key == 'draw_then_discard_choice':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} discarded {getattr(chosen, 'name', str(chosen))} via {source_name}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'choice_key': choice_key,
            }

        if choice_key == 'bait_exhaustion_target_discard':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            initiator_name = choice_context.get('initiator_player_name') or '其他玩家'
            target_name = choice_context.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_context.get('source_name') or '誘導虛耗'
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }

        if choice_key == 'tianfang_support_target_discard':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            player.hand.remove(chosen)
            player.deck.discard([chosen])
            self.pending_choice = None
            choice_context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            initiator_name = choice_context.get('initiator_player_name') or '其他玩家'
            target_name = choice_context.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_context.get('source_name') or '天方奧援'
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {getattr(chosen, 'name', str(chosen))}")
            return {
                'success': True,
                'discarded_card': getattr(chosen, 'name', str(chosen)),
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }

        if choice_key == 'era_red_discard_to_build_near_target':
            if chosen not in player.hand:
                return {'error': 'Chosen card not in hand'}
            return self._resolve_era_red_discard_to_build_choice(player, choice, [chosen])

        return {'error': 'Unsupported pending choice type'}

    def _resolve_multi_card_choice(self, player, choice, indices):
        cards = choice.get('cards') or []
        count = int(choice.get('count', 1) or 1)
        min_count = int(choice.get('min_count', count) if choice.get('min_count') is not None else count)
        if not isinstance(indices, list):
            return {'error': 'Invalid choice count'}
        if choice.get('choice_key') in {'red_army_ccdi_discard_draw', 'era_red_discard_to_build_near_target'}:
            if len(indices) < min_count or len(indices) > count:
                return {'error': 'Invalid choice count'}
        elif len(indices) != count:
            return {'error': 'Invalid choice count'}
        if len(set(indices)) != len(indices):
            return {'error': 'Duplicate choice indices'}
        if any(i is None or i < 0 or i >= len(cards) for i in indices):
            return {'error': 'Invalid choice index'}
        choice_key = choice.get('choice_key')
        selected_cards = [cards[i] for i in indices]

        if choice_key == 'red_army_ccdi_discard_draw':
            ok, err = self._red_army_can_use_action(player, '中紀委')
            if not ok:
                return {'error': err}
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            drawn = self._draw_player_cards(player, len(selected_cards)) if selected_cards else []
            self._mark_red_army_action_used('中紀委')
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            self.log(f"{player.name} triggered 中紀委, discarded {len(selected_cards)}, and drew {len(drawn)}")
            return {
                'success': True,
                'name': '中紀委',
                'chosen_cards': [getattr(card, 'name', str(card)) for card in selected_cards],
                'discarded': len(selected_cards),
                'drawn': len(drawn),
                'choice_key': choice_key,
            }

        if choice_key == 'era_red_discard_to_build_near_target':
            return self._resolve_era_red_discard_to_build_choice(player, choice, selected_cards)

        if choice_key == 'era_inspect_deck_top_and_reorder':
            inspected_cards = list(choice.get('cards') or [])
            top_count = int(choice.get('top_count', count) or count)
            if len(indices) != top_count:
                return {'error': 'Invalid choice count'}
            if any(card not in player.deck.draw_pile for card in inspected_cards):
                return {'error': 'Inspected deck cards changed'}
            for card in inspected_cards:
                player.deck.draw_pile.remove(card)
            selected_set = set(selected_cards)
            remaining_top_first = [card for card in inspected_cards if card not in selected_set]
            # Deck.draw() pops from the end, so append bottom-to-top. The first clicked
            # selected card becomes the next card drawn; the second clicked card is below it.
            player.deck.draw_pile.extend(reversed(remaining_top_first))
            player.deck.draw_pile.extend(reversed(selected_cards))
            self.pending_choice = None
            selected_names = [getattr(card, 'name', str(card)) for card in selected_cards]
            inspected_names = [getattr(card, 'name', str(card)) for card in inspected_cards]
            new_top_names = [getattr(card, 'name', str(card)) for card in reversed(player.deck.draw_pile[-top_count:])]
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            if context.get('era_id'):
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': context.get('era_id'),
                    'type': 'inspect_deck_top_and_reorder',
                    'inspected': inspected_names,
                    'selected_top': selected_names,
                })
            source_name = choice.get('source_name') or '時代關卡'
            self.log(f"{player.name} reordered deck top via {source_name}: {', '.join(selected_names)}")
            drawn_names = []
            draw_after = int(context.get('draw_after_reorder', 0) or 0)
            if draw_after:
                drawn = self._draw_player_cards(player, draw_after)
                drawn_names = [getattr(card, 'name', str(card)) for card in drawn]
                self.log(f"{player.name} drew {len(drawn)} card(s) after reordering via {source_name}")
            if context.get('faction_action_name'):
                self.turn_log['faction_action_used'] = True
                self._track_event_progress('use_faction_ability', player=player)
            return {
                'success': True,
                'choice_key': choice_key,
                'inspected_cards': inspected_names,
                'chosen_cards': selected_names,
                'deck_top': new_top_names,
                **({'drawn_cards': drawn_names} if drawn_names else {}),
            }

        if choice_key in {'discard_self', 'event_discard_self'}:
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            non_starters = [card for card in selected_cards if getattr(card, 'name', str(card)) not in {'追隨者', '樂捐者'}]
            if len(non_starters) == len(selected_cards):
                self.turn_log['non_starter_discard'] = True
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            if choice.get('grant_propaganda_if_all_non_starter') and len(non_starters) == len(selected_cards):
                player.resources['propaganda'] += int(choice.get('grant_propaganda_if_all_non_starter'))
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            self.pending_choice = None
            chosen_names = [getattr(card, 'name', str(card)) for card in selected_cards]
            self.log(
                f"{player.name} discarded {len(selected_cards)} chosen card(s): {', '.join(chosen_names)} "
                f"(hand {len(player.hand)}, deck {len(player.deck.draw_pile)}, discard {len(player.deck.discard_pile)})"
            )
            remaining_event_targets = list(context.get('remaining_event_discard_self_player_ids') or [])
            if choice_key == 'event_discard_self' and remaining_event_targets:
                followup = self._open_next_event_discard_self_choice(
                    remaining_event_targets,
                    int(context.get('event_discard_self_count', 1) or 1),
                    context.get('event_discard_self_outcome') or 'failure',
                    open_hk_relocation=bool(context.get('open_hk_free_base_relocation_after_resolution')),
                )
                if followup and followup.get('pending_choice'):
                    return {'success': True, 'chosen_cards': chosen_names, 'pending_choice': True}
            if context.get('open_hk_free_base_relocation_after_resolution'):
                self._open_hong_kong_base_relocation_window()
            return {'success': True, 'chosen_cards': chosen_names}

        if choice_key in {'armed_target_discard', 'era_bonus_discard_on_red_card'}:
            for card in selected_cards:
                if card not in player.hand:
                    return {'error': 'Chosen card not in hand'}
            for card in selected_cards:
                player.hand.remove(card)
                player.deck.discard([card])
            self.turn_log['successful_discard'] = True
            self.pending_choice = None
            initiator = next((p for p in self.players if getattr(p, 'id', None) == choice.get('initiator_player_id')), None)
            if initiator is not None and choice.get('draw_on_success'):
                self._draw_player_cards(initiator, int(choice.get('draw_on_success')))
            initiator_name = choice.get('initiator_player_name') or '其他玩家'
            target_name = choice.get('target_player_name') or player.name
            source_name = choice.get('source_name') or choice_key
            chosen_names = [getattr(card, 'name', str(card)) for card in selected_cards]
            self.log(f"{initiator_name} used {source_name} to force {target_name} to discard {len(chosen_names)} card(s)")
            if choice_key == 'era_bonus_discard_on_red_card':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_discard_on_red_card',
                    'status': 'resolved',
                    'discarded_count': len(chosen_names),
                    'target_player_id': getattr(player, 'id', None),
                })
            response = {
                'success': True,
                'chosen_cards': chosen_names,
                'target_player_name': target_name,
                'initiator_player_name': initiator_name,
                'choice_key': choice_key,
            }
            followup = self._start_era_followup_target_choice(choice.get('era_followup_target_choice'))
            if followup and followup.get('pending_choice'):
                response['pending_choice'] = True
            return response

        if choice_key == 'trash_from_hand_or_discard':
            starters = {'追隨者', '樂捐者'}
            chosen_cards = []
            zones = []
            removed_cards = []
            for entry in selected_cards:
                card = entry.get('card') if isinstance(entry, dict) else entry
                zone = entry.get('zone') if isinstance(entry, dict) else None
                zone_label = entry.get('zone_label') if isinstance(entry, dict) else None
                if zone == 'hand':
                    if card not in player.hand:
                        return {'error': 'Chosen card not in hand'}
                    player.hand.remove(card)
                elif zone == 'discard':
                    if card not in player.deck.discard_pile:
                        return {'error': 'Chosen card not in discard pile'}
                    player.deck.discard_pile.remove(card)
                else:
                    return {'error': 'Unsupported trash source'}
                if getattr(card, 'name', str(card)) not in starters:
                    self.turn_log['non_starter_discard'] = True
                returned = self._return_removed_card_to_purchase_supply(card)
                if returned is None:
                    returned = self._remove_card_from_game(card)
                chosen_cards.append(getattr(card, 'name', str(card)))
                zones.append(zone_label or zone)
                removed_cards.append(returned)
            self.pending_choice = None
            source_name = choice.get('source_name') or choice_key
            self.log(f"{player.name} trashed {len(chosen_cards)} chosen card(s) via {source_name}")
            return {
                'success': True,
                'chosen_cards': chosen_cards,
                'zones': zones,
                'removed_cards': removed_cards,
            }

        return {'error': 'Unsupported pending choice type'}

    def _resolve_option_choice(self, player, choice, index):
        options = choice.get('options') or []
        if index is None or index < 0 or index >= len(options):
            return {'error': 'Invalid choice index'}
        choice_key = choice.get('choice_key')

        if choice_key == 'shared_spy_origin_consent':
            context = dict(choice.get('context') or {})
            actor = next(
                (p for p in self.players if getattr(p, 'id', None) == context.get('actor_player_id')),
                None,
            )
            sacrifice_town = context.get('sacrifice_town')
            flow_context = dict(context.get('flow_context') or {})
            self.pending_choice = None
            if actor is None or not sacrifice_town:
                return {'error': 'Shared spy origin is no longer valid'}

            def restore_actor_choice(message, *, exclude_declined_origin=False):
                blocked_towns = set(flow_context.get('declined_shared_origin_towns') or [])
                if exclude_declined_origin:
                    blocked_towns.add(sacrifice_town)
                towns = self._interactive_support_sacrifice_towns(
                    actor,
                    max_steps=int((flow_context.get('effect_payload') or {}).get('range', 1) or 1),
                    target_players=self._target_players_for_interaction(actor, flow_context.get('target_player_id')),
                    target_region=(flow_context.get('effect_payload') or {}).get('target_region'),
                    include_shared_source=True,
                )
                towns = [entry for entry in towns if entry.get('town') not in blocked_towns]
                if towns:
                    flow_context['declined_shared_origin_towns'] = sorted(blocked_towns)
                    self._set_pending_support_flow_choice(
                        actor, 'card_dissolve_interaction', 'sacrifice_town',
                        f'派遣間諜：{message}，請重新選擇要瓦解的起點組織。',
                        source_name='派遣間諜', towns=towns, context=flow_context,
                        **self._dissolve_cancel_kwargs(flow_context),
                    )
                else:
                    # No alternative sacrifice-eligible organization exists: 派遣間諜's flow ends
                    # here with no effect (the actor's card was already committed/discarded when
                    # the flow started, and this is not a cancel -- it's a fizzle, exactly like
                    # `_resolve_support_flow_choice`'s "no legal target" branch). The deferred
                    # trigger's marker lives nested under this consent choice's own
                    # `flow_context` (never at this choice's own top-level context), so
                    # `_settle_deferred_card_play_triggers` -- which only ever inspects the
                    # top-level context of the choice actually being resolved (the OWNER's
                    # consent choice here, not the actor's flow) -- could never find it. Fire it
                    # directly here instead, at this definite terminal point.
                    deferred_triggers = flow_context.get('post_play_faction_triggers')
                    if isinstance(deferred_triggers, dict):
                        flow_context.pop('post_play_faction_triggers', None)
                        trigger_player = next(
                            (candidate for candidate in self.players if candidate.id == deferred_triggers.get('player_id')),
                            actor,
                        )
                        self._apply_card_play_faction_abilities(
                            trigger_player,
                            cost_has_money=bool(deferred_triggers.get('cost_has_money')),
                            cost_has_propaganda=bool(deferred_triggers.get('cost_has_propaganda')),
                            played_card=deferred_triggers.get('played_card'),
                            used_faction_ability_names=deferred_triggers.get('used_faction_ability_names'),
                        )
                return {'success': True, 'pending_choice': bool(towns), 'declined': True}

            if index == 0:
                self.log(f"{player.name} declined {actor.name}'s request to use the organization at {sacrifice_town} for 派遣間諜")
                return restore_actor_choice('組織擁有者不同意', exclude_declined_origin=True)

            current_owner = self._shared_origin_owner(actor, sacrifice_town)
            if current_owner is not player or sacrifice_town == getattr(player, 'base', None):
                return restore_actor_choice('共用組織狀態已改變')
            targets = self._interactive_support_dissolve_targets_near_town(
                actor,
                sacrifice_town,
                max_steps=int((flow_context.get('effect_payload') or {}).get('range', 1) or 1),
                target_players=self._target_players_for_interaction(actor, flow_context.get('target_player_id')),
                target_region=(flow_context.get('effect_payload') or {}).get('target_region'),
                excluded_target=(player.id, sacrifice_town),
            )
            if not targets:
                return restore_actor_choice('已無合法目標')
            # Consent alone does not remove the organization yet -- per the cancellable-dissolve
            # -target-selection feature, no own organization may be removed until the *final*
            # confirmation (picking the enemy target below). The consenting owner's organization
            # is decremented atomically together with the enemy dissolve in
            # `_resolve_support_interaction_result`'s 'interactive_dissolve_self_and_enemy' branch.
            self.log(f"{player.name} agreed that {actor.name} may dissolve the organization at {sacrifice_town} for 派遣間諜")
            next_context = {**flow_context, 'sacrifice_town': sacrifice_town, 'sacrifice_owner_player_id': player.id}
            max_steps = int((flow_context.get('effect_payload') or {}).get('range', 1) or 1)
            self._set_pending_support_flow_choice(
                actor, 'card_dissolve_interaction', 'target',
                f'派遣間諜：選擇 {sacrifice_town} {max_steps} 格內的 1 個敵方組織瓦解。',
                source_name='派遣間諜', targets=targets, context=next_context,
                **self._dissolve_cancel_kwargs(next_context),
            )
            return {'success': True, 'pending_choice': True, 'town': sacrifice_town}

        if choice_key == 'org_exp_repeat_prompt':
            context = dict(choice.get('context') or {})
            source_name = choice.get('source_name') or context.get('card_name') or '組織經驗甲'
            self.pending_choice = None
            if index == 0:
                self.log(f"{player.name} declined to repeat build via {source_name}")
                return {'success': True, 'choice_key': choice_key, 'declined': True}
            min_cost = int(((context.get('effect') or {}).get('repeat_on_discard_min_cost')) or 4)
            qualifying = self._org_exp_repeat_qualifying_cards(player, min_cost)
            if not qualifying:
                return {'error': 'No qualifying card to discard'}
            self._set_pending_card_choice(
                player,
                'org_exp_repeat_discard',
                qualifying,
                f'{source_name}：選擇 1 張購買費用{min_cost}點以上的手牌棄掉。',
                source_name=source_name,
                context=context,
            )
            return {'success': True, 'choice_key': choice_key, 'pending_choice': True}

        if choice_key == 'ethnic_ritual_miss_reward':
            base_result = dict(((choice.get('context') or {}).get('base_result')) or {})
            if index == 1:
                player.resources['money'] += 2
                reward = {'money': 2, 'propaganda': 0}
            else:
                player.resources['propaganda'] += 2
                reward = {'money': 0, 'propaganda': 2}
            self.pending_choice = None
            self.log(f"{player.name} chose 民族祭儀 miss reward: {'2 money' if index == 1 else '2 propaganda'}")
            return {'success': True, 'result': {**base_result, 'reward': reward}}

        if choice_key == 'guerrilla_reward':
            red_player_id = (choice.get('context') or {}).get('red_player_id')
            red_player = next((candidate for candidate in self.players if candidate.id == red_player_id), None)
            self.pending_choice = None
            if index == 0:
                drawn = self._draw_player_cards(player, 1)
                self.log(f"{player.name} triggered 游擊隊 and chose to draw 1 card")
                return {'success': True, 'choice_key': choice_key, 'choice': 'draw', 'drawn': len(drawn)}
            if red_player is None or not red_player.hand:
                return {'error': '紅軍目前沒有手牌可以棄置'}
            discarded = red_player.hand.pop()
            red_player.deck.discard([discarded])
            card_name = getattr(discarded, 'name', str(discarded))
            self.log(f"{player.name} triggered 游擊隊 and chose to force {red_player.name} to discard {card_name}")
            return {'success': True, 'choice_key': choice_key, 'choice': 'red_discard', 'discarded': card_name}

        if choice_key == 'show_strength_reward':
            self.pending_choice = None
            if index == 0:
                player.resources['propaganda'] += 3
                reward = {'propaganda': 3, 'money': 0}
                reward_name = '3 propaganda'
            else:
                player.resources['money'] += 3
                reward = {'propaganda': 0, 'money': 3}
                reward_name = '3 money'
            self.log(f"{player.name} triggered 展現實力 and chose {reward_name}")
            return {'success': True, 'choice_key': choice_key, 'reward': reward}

        if choice_key == 'choose_one':
            selected = options[index]
            context = dict(choice.get('context') or {})
            context['choice_index'] = index
            self.pending_choice = None
            result = None
            pending_target_result = None
            for nested in selected.get('effect', []):
                nested_type = nested.get('type') if isinstance(nested, dict) else None
                source_name = context.get('card_name') or choice.get('source_name')
                if nested_type == 'dissolve' and source_name == '情報網':
                    range_limit = int(context.get('range_limit', 1) or 1)
                    target_region = context.get('target_region')
                    targets = self._interactive_support_dissolve_targets(
                        player,
                        require_self_sacrifice=False,
                        max_steps=range_limit,
                        target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                        target_region=target_region,
                        include_shared_source=True,
                    )
                    if targets:
                        pending_target_result = self._set_pending_target_choice(
                            player,
                            'intel_network_dissolve_target',
                            targets,
                            f'情報網：選擇 1 個要瓦解的 {range_limit} 格內敵方組織。',
                            source_name='情報網',
                            context=context,
                            **self._dissolve_cancel_kwargs(context),
                        )
                        result = pending_target_result
                        continue
                nested_result = self.effect_engine.execute(nested, player, self, context=context)
                if isinstance(nested_result, dict) and nested_result.get('pending_choice'):
                    result = nested_result
            self.log(f"{player.name} resolved choose_one option {index}")
            still_pending = isinstance(result, dict) and result.get('pending_choice')
            if not still_pending:
                # Option A/C (or B with no legal target at all): nothing further is pending, so
                # this choose_one resolve IS the flow's final step -- mirrors every other
                # dissolve-flow commit point (see _settle_deferred_card_play_triggers). Option B
                # with a legal target opened its own nested intel_network_dissolve_target choice
                # instead (still_pending True), whose OWN eventual commit tags itself.
                choice['is_final_confirmation'] = True
            return {
                'success': True,
                'choice_index': index,
                'label': selected.get('label'),
                **({'pending_choice': True} if still_pending else {}),
            }

        return {'error': 'Unsupported pending choice type'}

    def _live_pending_town_choices(self, player, choice):
        """`card_build_organization`／`era_red_build_near_target` 這類連續多次建立的候選
        城鎮清單，過去只在佇列批次「啟動」的當下算一次、之後就固定存在 `choice['towns']`
        裡沿用，直到玩家解決掉才會換下一批。這代表如果玩家在兩次建立之間先移動了組織，
        候選清單不會反映移動後的新位置——2026-08-04 playtest 回報：先在桃園建立，移動到
        彰化後，第二次建立候選仍是移動前、臺北附近的城鎮。修法是不要相信儲存的舊清單，
        每次要呈現給玩家（`state()` 序列化）或要解析玩家的選擇（`_resolve_town_choice()`）
        時都用 `choice['context']['effect']` 重新即時投影一次。回傳 `None` 表示這個
        choice_key 不適用即時投影，呼叫端應該繼續沿用 `choice.get('towns')`。"""
        choice_key = choice.get('choice_key')
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        if choice_key == 'card_build_organization':
            return self._card_build_town_choices(player, context.get('effect') or {})
        if choice_key == 'era_red_build_near_target':
            effect = context.get('effect') if isinstance(context.get('effect'), dict) else {}
            built_towns = set(context.get('built_towns') or [])
            return [
                entry for entry in self._era_build_towns_near_target(player, effect)
                if entry.get('town') not in built_towns
            ]
        return None

    def _resolve_town_choice(self, player, choice, index):
        live_towns = self._live_pending_town_choices(player, choice)
        if live_towns is not None:
            choice['towns'] = live_towns
        towns = choice.get('towns') or []
        if index is None or index < 0 or index >= len(towns):
            return {'error': 'Invalid choice index'}
        selected = towns[index] or {}
        town = selected.get('town')
        if not town:
            return {'error': 'Invalid town choice'}
        choice_key = choice.get('choice_key')
        if choice_key == 'event_build_organization' and player.organizations.get(town, 0) > 0:
            # Recovery for old/stale browser states: the map may already have sent a
            # generic build that mutated the board, while the event town choice stayed
            # pending and continued to block the phase button.  Treat the matching
            # event choice as consumed without adding a duplicate organization.
            self.pending_choice = None
            self.log(f"{player.name} already had organization in {town}; consumed stale event build choice")
            return {
                'success': True,
                'choice_index': index,
                'town': town,
                'selected': selected,
                'choice_key': choice_key,
                'recovered_stale_choice': True,
            }
        if choice_key in {'event_build_organization', 'card_build_organization', 'era_red_build_near_target'}:
            if not self._can_player_build_in_town(player, town):
                return {'error': 'Cannot build in enemy-occupied or invalid town'}
        if choice_key == 'event_build_organization':
            self._place_organization(player, town)
            self.log(f"{player.name} built organization in {town} via event")
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            remaining_event_players = list(context.get('remaining_event_build_near_own_player_ids') or [])
            if remaining_event_players:
                self.pending_choice = None
                followup = self._open_next_event_build_near_own_choice(
                    remaining_event_players,
                    context.get('event_build_near_own_effect') or {},
                    int(context.get('event_build_near_own_count', 1) or 1),
                    event_name=context.get('event_name') or choice.get('source_name'),
                )
                response = {
                    'success': True,
                    'choice_index': index,
                    'town': town,
                    'selected': selected,
                    'choice_key': choice_key,
                }
                if followup and followup.get('pending_choice'):
                    response['pending_choice'] = True
                return response
        elif choice_key == 'card_build_organization':
            remaining_before = self._remaining_card_build_entitlements()
            self._place_organization(player, town)
            self._record_action_build(player, town)
            self.log(f"{player.name} built organization in {town} via {choice.get('source_name') or 'card'}")
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            self.pending_choice = None
            if self._maybe_prompt_org_exp_repeat_build(player, context):
                return {
                    'success': True,
                    'choice_index': index,
                    'town': town,
                    'selected': selected,
                    'choice_key': choice_key,
                    'pending_choice': True,
                    'remaining_builds': max(0, remaining_before - 1),
                }
            remaining_effects = list(context.get('remaining_effects') or [])
            for idx, effect in enumerate(remaining_effects):
                context['remaining_effects'] = remaining_effects[idx + 1:]
                result = self.effect_engine.execute(effect, player, self, context=context)
                if isinstance(result, dict) and result.get('pending_choice'):
                    if self.pending_choice and self.pending_choice.get('choice_key') == 'card_build_organization':
                        remaining = self._refresh_card_build_choice_projection()
                    else:
                        remaining = self._remaining_card_build_entitlements()
                    return {
                        'success': True,
                        'choice_index': index,
                        'town': town,
                        'selected': selected,
                        'choice_key': choice_key,
                        'pending_choice': True,
                        'remaining_builds': remaining,
                    }
            continuation = self._resume_card_build_queue_if_idle(player)
            response = {
                'success': True,
                'choice_index': index,
                'town': town,
                'selected': selected,
                'choice_key': choice_key,
                'remaining_builds': self._remaining_card_build_entitlements(),
            }
            if continuation:
                response.update(continuation)
            return response
        elif choice_key == 'era_red_build_near_target':
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            remaining_builds = max(0, int(context.get('remaining_builds', 1) or 1))
            if remaining_builds <= 0:
                return {'error': 'No era builds remaining'}
            if player.organizations.get(town, 0) > 0:
                return {'error': 'Era build town already has your organization'}
            self._place_organization(player, town)
            applied_entry = {
                'era': context.get('era_id'),
                'type': 'red_discard_to_build_near_target',
                'town': town,
                'discarded_cards': list(context.get('discarded_cards') or []),
                'build_index': len(list(context.get('built_towns') or [])) + 1,
                'build_total': int(context.get('build_total', remaining_builds) or remaining_builds),
            }
            self.turn_log.setdefault('era_effects_applied', []).append(applied_entry)
            built_towns = list(context.get('built_towns') or []) + [town]
            remaining_builds -= 1
            if remaining_builds > 0:
                effect = context.get('effect') if isinstance(context.get('effect'), dict) else {}
                towns = [entry for entry in self._era_build_towns_near_target(player, effect) if entry.get('town') not in set(built_towns)]
                source_name = choice.get('source_name') or context.get('era_name') or '時代關卡'
                if towns:
                    self._set_pending_town_choice(
                        player,
                        'era_red_build_near_target',
                        towns,
                        f"{source_name}：還可免費建立 {remaining_builds} 個紅軍組織。",
                        source_name=source_name,
                        context={
                            **context,
                            'remaining_builds': remaining_builds,
                            'built_towns': built_towns,
                        },
                    )
                    self.log(f"{player.name} built organization in {town} via era effect; {remaining_builds} build(s) remain")
                    return {
                        'success': True,
                        'choice_index': index,
                        'town': town,
                        'selected': selected,
                        'choice_key': choice_key,
                        'pending_choice': True,
                        'remaining_builds': remaining_builds,
                    }
                self.log(f"{player.name} built organization in {town} via era effect; no more valid towns for remaining builds")
                self.pending_choice = None
                return {
                    'success': True,
                    'choice_index': index,
                    'town': town,
                    'selected': selected,
                    'choice_key': choice_key,
                    'remaining_builds_unresolved': remaining_builds,
                    'no_more_valid_towns': True,
                }
            self.log(f"{player.name} built organization in {town} via era effect")
            self.pending_choice = None
            return {
                'success': True,
                'choice_index': index,
                'town': town,
                'selected': selected,
                'choice_key': choice_key,
                'remaining_builds': 0,
            }
        self.pending_choice = None
        return {
            'success': True,
            'choice_index': index,
            'town': town,
            'selected': selected,
            'choice_key': choice_key,
        }

    def _resolve_target_choice(self, player, choice, index):
        targets = choice.get('targets') or []
        if index is None or index < 0 or index >= len(targets):
            return {'error': 'Invalid choice index'}
        selected = targets[index] or {}
        target_id = selected.get('id')
        if target_id is None:
            return {'error': 'Invalid target choice'}
        choice_key = choice.get('choice_key')
        if choice_key == 'bait_exhaustion_target':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not getattr(target_player, 'hand', None):
                return {'error': 'Target player has no hand cards'}
            source_name = (choice.get('context') or {}).get('source_name') or '誘導虛耗'
            self.pending_choice = {
                'type': 'card_choice',
                'choice_key': 'bait_exhaustion_target_discard',
                'player_id': target_player.id,
                'cards': list(target_player.hand),
                'prompt': f"{source_name}：請選擇 1 張手牌棄掉。",
                'source_name': source_name,
                'context': {
                    'initiator_player_id': player.id,
                    'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                    'target_player_id': target_player.id,
                    'target_player_name': getattr(target_player, 'name', str(target_id)),
                    **(choice.get('context') if isinstance(choice.get('context'), dict) else {}),
                },
            }
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'pending_choice': True,
            }
        if choice_key in {'intel_network_dissolve_target', 'event_red_dissolve', 'era_red_bonus_dissolve_target'}:
            target_player_id = selected.get('player_id') or target_id
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not town:
                return {'error': 'Target town not found'}
            if choice_key == 'intel_network_dissolve_target':
                context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
                current_targets = self._interactive_support_dissolve_targets(
                    player,
                    require_self_sacrifice=False,
                    max_steps=int(context.get('range_limit', 1) or 1),
                    target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                    target_region=context.get('target_region'),
                    include_shared_source=True,
                )
                if not any(
                    entry.get('player_id') == target_player_id and entry.get('town') == town
                    for entry in current_targets
                ):
                    return {'error': 'Target organization is no longer within range'}
            if choice_key == 'era_red_bonus_dissolve_target':
                context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
                max_steps = int(context.get('max_steps', 1) or 1)
                target_camp = context.get('target_camp')
                if target_camp and not self._player_matches_camp(target_player, target_camp):
                    return {'error': 'Target player is not valid for era effect'}
                source_towns = [src for src, count in (getattr(player, 'organizations', {}) or {}).items() if count > 0]
                if town not in self._towns_within_steps(source_towns, max_steps=max_steps):
                    return {'error': 'Target organization is not within era range'}
            result = self.dissolve_organization(
                player, target_player, town, source='card', _from_pending_choice=True
            )
            if result.get('error'):
                return result
            # Committing real board state right now (covers 情報網's cancellable
            # intel_network_dissolve_target as well as the forced event_red_dissolve/
            # era_red_bonus_dissolve_target choices, for which this is a harmless no-op since
            # those never carry a post_play_faction_triggers marker in the first place).
            choice['is_final_confirmation'] = True
            self.pending_choice = None
            if choice_key == 'era_red_bonus_dissolve_target':
                self.turn_log.setdefault('era_effects_applied', []).append({
                    'era': (choice.get('context') or {}).get('era_id') if isinstance(choice.get('context'), dict) else None,
                    'type': 'bonus_dissolve_on_red_card_near_self',
                    'status': 'resolved',
                    'town': town,
                    'target_player_id': target_player_id,
                })
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                'town': town,
            }
        if choice_key == 'red_army_propaganda_department_target':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None or getattr(target_player, 'faction_id', None) == 'red_army':
                return {'error': 'Target player not found'}
            ok, err = self._red_army_can_use_action(player, '政工部', target_player.id)
            if not ok:
                return {'error': err}
            topdecked = '內鬥'
            added = self._topdeck_static_purchase_card(target_player, topdecked, '政工部')
            self._mark_red_army_action_used('政工部', target_player.id)
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            if added:
                self.log(f"{player.name} triggered 政工部 and placed {'、'.join(added)} on {target_player.name}'s deck")
            else:
                self.log(f"{player.name} triggered 政工部 but {topdecked} supply was empty")
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'name': '政工部',
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'topdecked_card': '、'.join(added) if added else None,
                'static_supply_empty': not added,
            }
        if choice_key == 'red_army_state_security_target':
            target_player_id = selected.get('player_id') or target_id
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            if not town:
                return {'error': 'Target town not found'}
            ok, err = self._red_army_can_use_action(player, '國安部', target_player.id)
            if not ok:
                return {'error': err}
            result = self.dissolve_organization(
                player, target_player, town, source='faction_action', _from_pending_choice=True
            )
            if result.get('error'):
                return result
            self._mark_red_army_action_used('國安部', target_player.id)
            self._track_event_progress('use_faction_ability', player=player)
            self.pending_choice = None
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'name': '國安部',
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                'town': town,
            }
        if choice_key == 'red_support_target_player':
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_id), None)
            if target_player is None:
                return {'error': 'Target player not found'}
            context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
            card = context.get('card')
            if card is None:
                return {'error': 'Support card context missing'}
            target_player.deck.discard([card])
            self.pending_choice = None
            self.log(f"{player.name} 將紅軍奧援放入 {target_player.name} 的棄牌堆")
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'target_player_name': getattr(target_player, 'name', str(target_id)),
                'moved_to_player_id': getattr(target_player, 'id', None),
                'moved_to_player_name': getattr(target_player, 'name', str(target_id)),
            }
        if choice_key == 'imitate_topdeck_target':
            result = self._perform_imitate_topdeck(player, target_id)
            self.pending_choice = None
            if result.get('error'):
                return result
            return {
                'success': True,
                'choice_index': index,
                'target_id': target_id,
                'selected': selected,
                'choice_key': choice_key,
                'imitated_card': result.get('imitated_card'),
                'target_player_name': result.get('target_player_name'),
            }
        self.pending_choice = None
        return {
            'success': True,
            'choice_index': index,
            'target_id': target_id,
            'selected': selected,
            'choice_key': choice_key,
        }

    def _refresh_support_flow_choice_after_stale_result(self, player, choice):
        """Refresh an interactive support choice after resolve-time legality changed."""
        context = dict(choice.get('context') or {})
        effect_type = context.get('effect_type')
        step = choice.get('step')
        refreshed = dict(choice)
        if step == 'town':
            near_only = effect_type == 'interactive_build_near_inner'
            towns = self._interactive_support_build_towns(player, near_only=near_only)
            refreshed['towns'] = towns
            if towns:
                self.pending_choice = refreshed
                return True
            return False
        if step == 'sacrifice_town':
            towns = self._interactive_support_sacrifice_towns(
                player,
                max_steps=int((context.get('effect_payload') or {}).get('range', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                target_region=(context.get('effect_payload') or {}).get('target_region'),
                include_shared_source=bool(context.get('include_shared_source', False)),
            )
            refreshed['towns'] = towns
            if towns:
                self.pending_choice = refreshed
                return True
            return False
        if step != 'target':
            return False

        if effect_type == 'interactive_dissolve_self_and_enemy' and context.get('sacrifice_town'):
            targets = self._interactive_support_dissolve_targets_near_town(
                player,
                context.get('sacrifice_town'),
                max_steps=int((context.get('effect_payload') or {}).get('range', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                target_region=(context.get('effect_payload') or {}).get('target_region'),
            )
        elif effect_type == 'interactive_dissolve_and_build':
            payload = context.get('effect_payload') or {}
            targets = [
                entry
                for entry in self._interactive_support_dissolve_targets(
                    player,
                    require_self_sacrifice=False,
                    max_steps=int(payload.get('range', 1) or 1),
                    target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                    target_region=payload.get('target_region'),
                    include_shared_source=bool(context.get('include_shared_source', False)),
                )
                if self._can_replace_dissolved_org_with_own(
                    player,
                    next((p for p in self.players if getattr(p, 'id', None) == entry.get('player_id')), None),
                    entry.get('town'),
                )
            ]
        elif effect_type == 'interactive_dissolve_many_near':
            accumulated_picks = context.get('accumulated_dissolve_picks') or []
            targets = [
                entry
                for entry in self._interactive_support_dissolve_targets(
                    player,
                    require_self_sacrifice=False,
                    max_steps=int((context.get('effect_payload') or {}).get('range', 1) or 1),
                    target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                    target_region=(context.get('effect_payload') or {}).get('target_region'),
                    include_shared_source=bool(context.get('include_shared_source', False)),
                )
                if not any(
                    pick.get('target_player_id') == entry.get('player_id') and pick.get('town') == entry.get('town')
                    for pick in accumulated_picks
                )
            ]
        elif effect_type == 'force_discard_near':
            payload = context.get('effect_payload') or {}
            targets = self._interactive_support_discard_targets_near(
                player,
                max_steps=int(payload.get('range', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                target_region=payload.get('target_region'),
                include_shared_source=bool(context.get('include_shared_source', False)),
            )
        else:
            targets = []
        refreshed['targets'] = targets
        if targets:
            self.pending_choice = refreshed
            return True
        return False

    def _resolve_support_flow_choice(self, player, choice, index):
        step = choice.get('step')
        if step in {'town', 'sacrifice_town'}:
            result = self._resolve_town_choice(player, choice, index)
        elif step == 'target':
            result = self._resolve_target_choice(player, choice, index)
        else:
            return {'error': 'Unsupported support flow step'}
        if result.get('error'):
            return result
        response = self._resolve_support_interaction_result(player, result, choice)
        if isinstance(response, dict) and response.get('error'):
            if self._refresh_support_flow_choice_after_stale_result(player, choice):
                return {**response, 'pending_choice': True, 'retryable': True}
            # No legal target remains -- the effect fizzles, but the card itself was still
            # genuinely played (this is not a cancel; nothing here is reversible), so this is
            # ALSO a legitimate final commit point for any deferred faction-play trigger.
            choice['is_final_confirmation'] = True
            self.pending_choice = None
            self.log(f"{player.name} 的 {choice.get('source_name', '奧援')} 因結算時已無合法目標而結束")
            return {
                'success': True,
                'effect_fizzled': True,
                'reason': response.get('error'),
                'source_name': choice.get('source_name'),
            }
        if not isinstance(response, dict) or response.get('pending_choice'):
            return response
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        followup = self._start_era_followup_discard_choice(context.get('era_followup_discard_choice'))
        if followup and followup.get('pending_choice'):
            response['pending_choice'] = True
        return response

    def cancel_pending_choice(self, player_id, expected_choice_id=None):
        choice = self.pending_choice or {}
        if not choice:
            return {'error': 'No pending choice'}
        if choice.get('player_id') != player_id:
            return {'error': 'Not your pending choice'}
        if expected_choice_id is not None and choice.get('choice_id') != expected_choice_id:
            return {'error': 'Stale pending choice'}
        is_registered_cancellable = choice.get('choice_key') in CANCELLABLE_CHOICE_KEYS
        if not is_registered_cancellable and not choice.get('cancellable'):
            return {'error': 'This choice cannot be cancelled'}
        player = next((p for p in self.players if p.id == player_id), None)
        rollback_card = choice.get('rollback_card')
        if rollback_card is not None:
            # Initial 北國奧援 choices are transactionally cancellable: no organization has
            # changed yet, so return the exact card object to its former hand slot. Borrowed
            # cards may already have been returned to their owner's deck top by the common
            # support discard path; remove that exact object and restore its return marker.
            if player is None:
                return {'error': 'Support card cannot be restored'}

            removed_from_zone = False
            for zone_owner in self.players:
                zones = [zone_owner.hand, zone_owner.deck.draw_pile, zone_owner.deck.discard_pile]
                for zone in zones:
                    for zone_index, candidate in enumerate(zone):
                        if candidate is rollback_card:
                            zone.pop(zone_index)
                            removed_from_zone = True
                            break
                    if removed_from_zone:
                        break
                if removed_from_zone:
                    break

            borrowed_purchase_index = choice.get('rollback_borrowed_purchase_area_index')
            if not removed_from_zone and borrowed_purchase_index is None:
                return {'error': 'Support card cannot be restored'}

            borrowed_owner_id = choice.get('rollback_borrowed_owner_id')
            if borrowed_owner_id:
                setattr(rollback_card, '_return_to_owner_topdeck', borrowed_owner_id)
            if borrowed_purchase_index is not None:
                setattr(rollback_card, '_return_to_purchase_area_index', borrowed_purchase_index)

            hand_index = max(0, min(int(choice.get('rollback_hand_index', len(player.hand))), len(player.hand)))
            player.hand.insert(hand_index, rollback_card)
            # Undo exactly (and only) what THIS card's own play contributed to the
            # reference-counted turn_log bookkeeping -- correct under any cancellation order of
            # multiple interleaved cancellable cards, unlike restoring an absolute snapshot (see
            # _note_*/_undo_* helpers and Game._new_turn_log's field comment).
            if choice.get('rollback_contributed_money_cost'):
                self._undo_money_cost_card_played()
            if choice.get('rollback_contributed_propaganda_cost'):
                self._undo_propaganda_cost_card_played()
            contributed_name = choice.get('rollback_contributed_nonstarter_name')
            if contributed_name:
                self._undo_nonstarter_name_played(contributed_name)
            # Undo exactly (and only) what THIS card's own play contributed to event_progress --
            # correct under any cancellation order of multiple interleaved cancellable plays,
            # unlike restoring an absolute snapshot (see _event_progress_delta/
            # _undo_event_progress_delta).
            self._undo_event_progress_delta(choice.get('rollback_event_progress_delta'))
        # Registered ability choices consume nothing until resolved; transactional support
        # choices explicitly restore their card and turn flags above.
        self.pending_choice = None
        source_name = choice.get('source_name') or choice.get('choice_key')
        self.log(f"{getattr(player, 'name', player_id)} 取消了 {source_name}，未消耗能力或卡牌")
        response = {
            'success': True,
            'cancelled': True,
            'choice_key': choice.get('choice_key'),
            'source_name': source_name,
        }
        if player is not None:
            resumed = self._resume_card_build_queue_if_idle(player)
            if isinstance(resumed, dict) and resumed.get('pending_choice'):
                response['pending_choice'] = True
        return response

    def resolve_pending_choice(self, player_id, index, target_player_ids=None, expected_choice_id=None):
        choice = self.pending_choice or {}
        if not choice:
            return {'error': 'No pending choice'}
        if choice.get('player_id') != player_id:
            return {'error': 'Not your pending choice'}
        if expected_choice_id is not None and choice.get('choice_id') != expected_choice_id:
            return {'error': 'Stale pending choice'}
        player = next((p for p in self.players if p.id == player_id), None)
        if not player:
            return {'error': 'Player not found'}
        resolvers = {
            'card_choice': self._resolve_card_choice,
            'multi_card_choice': self._resolve_multi_card_choice,
            'option_choice': self._resolve_option_choice,
            'town_choice': self._resolve_town_choice,
            'target_choice': self._resolve_target_choice,
            'support_flow_choice': self._resolve_support_flow_choice,
            'reaction_choice': self._resolve_reaction_choice,
        }
        choice_type = choice.get('type')
        if choice_type not in resolvers:
            return {'error': 'Unsupported pending choice type'}
        resolver = resolvers[choice_type]
        if choice_type == 'card_choice':
            result = resolver(
                player,
                choice,
                index,
                target_player_ids=target_player_ids,
            )
        else:
            result = resolver(player, choice, index)
        if not result.get('error'):
            self._settle_deferred_card_play_triggers(player, choice)
        if not result.get('error') and not self.pending_choice:
            build_continuation = self._resume_card_build_queue_if_idle(player)
            if build_continuation:
                result = {**result, **build_continuation}
        if not result.get('error') and not self.pending_choice:
            continuation = self._continue_era_and_event_flows()
            if continuation and continuation.get('pending_choice'):
                result = {**result, 'pending_choice': True}
        if not result.get('error') and self.pending_choice:
            result = {**result, 'pending_choice': True}
        return result

    def _start_card_dissolve_interaction(self, player, card_name, requires_self_sacrifice=False, range_limit=1, target_player_id=None, target_region=None, extra_context=None):
        target_players = self._target_players_for_interaction(player, target_player_id)
        effect_type = 'interactive_dissolve_self_and_enemy' if requires_self_sacrifice else 'interactive_dissolve_many_near'
        base_context = {
            'card_name': card_name,
            'effect_type': effect_type,
            'effect_payload': {'range': range_limit, 'target_region': target_region},
            'include_shared_source': True,
            'target_player_id': target_player_id,
            **(extra_context if isinstance(extra_context, dict) else {}),
        }
        if requires_self_sacrifice:
            towns = self._interactive_support_sacrifice_towns(
                player,
                max_steps=range_limit,
                target_players=target_players,
                target_region=target_region,
                include_shared_source=True,
            )
            if not towns:
                return None
            result = self._set_pending_support_flow_choice(
                player,
                'card_dissolve_interaction',
                'sacrifice_town',
                f'{card_name}：先選擇 1 個要瓦解的己方組織。',
                source_name=card_name,
                towns=towns,
                context=base_context,
                **self._dissolve_cancel_kwargs(base_context),
            )
            return {'pending_choice': True, **result}
        targets = self._interactive_support_dissolve_targets(
            player,
            require_self_sacrifice=False,
            max_steps=range_limit,
            target_players=target_players,
            target_region=target_region,
            include_shared_source=True,
        )
        if not targets:
            return None
        result = self._set_pending_support_flow_choice(
            player,
            'card_dissolve_interaction',
            'target',
            f'{card_name}：選擇 1 個要瓦解的鄰近敵方組織。',
            source_name=card_name,
            targets=targets,
            context=base_context,
            **self._dissolve_cancel_kwargs(base_context),
        )
        return {'pending_choice': True, **result}

    def _support_interaction_targets(self, player, effect_type, payload):
        # Single source of truth for an interactive support card's legal targets. Returns
        # the list of build towns / dissolve targets (an empty list means "no legal
        # target"), or None for non-interactive effect types (which always resolve).
        # Shared by _start_support_interaction (which opens the pending choice) and
        # _support_card_has_legal_target (the non-mutating pre-check in play_card) so the
        # two can never disagree about whether a play is legal.
        if effect_type in ('interactive_build_anywhere_inner', 'interactive_build_near_inner'):
            return self._interactive_support_build_towns(
                player,
                near_only=(effect_type == 'interactive_build_near_inner'),
            )
        if effect_type == 'interactive_dissolve_many_near':
            return self._interactive_support_dissolve_targets(
                player,
                require_self_sacrifice=False,
                max_steps=int(payload.get('range', 1) or 1),
                target_region=payload.get('target_region'),
                include_shared_source=True,
            )
        if effect_type == 'interactive_dissolve_self_and_enemy':
            return self._interactive_support_sacrifice_towns(
                player,
                max_steps=int(payload.get('range', 1) or 1),
                target_region=payload.get('target_region'),
                include_shared_source=True,
            )
        if effect_type == 'interactive_dissolve_and_build':
            targets = self._interactive_support_dissolve_targets(
                player,
                require_self_sacrifice=False,
                max_steps=int(payload.get('range', 1) or 1),
                target_region=payload.get('target_region'),
                include_shared_source=True,
            )
            return [
                entry
                for entry in targets
                if self._can_replace_dissolved_org_with_own(
                    player,
                    next((p for p in self.players if getattr(p, 'id', None) == entry.get('player_id')), None),
                    entry.get('town'),
                )
            ]
        if effect_type == 'force_discard_near':
            return self._interactive_support_discard_targets_near(
                player,
                max_steps=int(payload.get('range', 1) or 1),
                target_region=payload.get('target_region'),
                include_shared_source=True,
            )
        return None

    def _start_support_interaction(self, player, card_name, tier, region_index, effect_type, payload):
        effect_text = self._support_card_effect_text(card_name, tier, region_index)
        base_context = {
            'card_name': card_name,
            'tier': tier,
            'region_index': region_index,
            'effect_type': effect_type,
            'effect_payload': dict(payload or {}),
            'include_shared_source': True,
            'effect_text': effect_text,
        }
        targets = self._support_interaction_targets(player, effect_type, payload)
        if not targets:
            # None => not an interactive effect type; [] => no legal target.
            return None
        if effect_type == 'interactive_build_anywhere_inner':
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'town',
                f'{card_name}：選擇 1 個建立組織的牆內城鎮。',
                source_name=card_name,
                towns=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_build_near_inner':
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'town',
                f'{card_name}：選擇 1 個己方組織 1 格內的牆內城鎮建立組織。',
                source_name=card_name,
                towns=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_many_near':
            total_count = int((payload or {}).get('count', 1) or 1)
            is_multi = total_count > 1
            multi_kwargs = (
                {'remaining_count': total_count, 'selected_count': 0, 'total_count': total_count}
                if is_multi else {}
            )
            prompt = (
                f'{card_name}：已選 0/{total_count}，選擇 1 個要瓦解的鄰近敵方組織。'
                if is_multi else f'{card_name}：選擇 1 個要瓦解的鄰近敵方組織。'
            )
            # Note: `cancellable`/`rollback_*` are stamped onto this choice post-hoc, by
            # `_commit_support_card_play` (which runs right after this returns and has access to
            # the pre-play `action_context` this function does not) -- not here.
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                prompt,
                source_name=card_name,
                targets=targets,
                context=base_context,
                **multi_kwargs,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_self_and_enemy':
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'sacrifice_town',
                f'{card_name}：先選擇 1 個要瓦解的己方組織。',
                source_name=card_name,
                towns=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'interactive_dissolve_and_build':
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：先選擇 1 個要瓦解的敵方組織，成功後可在同地建立組織。',
                source_name=card_name,
                targets=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        if effect_type == 'force_discard_near':
            count = int((payload or {}).get('count', 0) or 0)
            random_pick = bool((payload or {}).get('random'))
            discard_text = f'隨機棄 {count} 張手牌' if random_pick else '選 1 張手牌棄掉'
            result = self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：選擇 1 位己方組織 1 格內的玩家，令其{discard_text}。',
                source_name=card_name,
                targets=targets,
                context=base_context,
            )
            return {'pending_choice': True, **result}
        return None

    def _resolve_support_interaction_result(self, player, result, choice):
        context = dict((choice or {}).get('context') or {})
        effect_type = context.get('effect_type')
        card_name = context.get('card_name') or '奧援卡'
        choice_key = (choice or {}).get('choice_key')
        if effect_type in {'interactive_build_anywhere_inner', 'interactive_build_near_inner'}:
            town = result.get('town')
            valid_towns = {
                entry.get('town')
                for entry in self._interactive_support_build_towns(
                    player,
                    near_only=(effect_type == 'interactive_build_near_inner'),
                )
            }
            if not town or town not in valid_towns:
                return {'error': 'Invalid build town'}
            self._place_organization(player, town)
            self._record_action_build(player, town)
            self.log(f"{player.name} resolved {card_name} and built in {town}")
            # This resolve is committing real board state right now -- see
            # _settle_deferred_card_play_triggers for why this is tagged on the choice itself
            # rather than inferred from where a paused choice happens to be parked.
            choice['is_final_confirmation'] = True
            return {'success': True, 'town': town}
        if effect_type == 'interactive_dissolve_self_and_enemy' and choice.get('step') == 'sacrifice_town':
            sacrifice_town = result.get('town')
            include_shared_source = bool(context.get('include_shared_source', False))
            sacrifice_owner = (
                self._shared_origin_owner(player, sacrifice_town)
                if sacrifice_town and include_shared_source
                else player if sacrifice_town in player.organizations else None
            )
            if not sacrifice_town or sacrifice_owner is None:
                return {'error': 'Invalid own organization to sacrifice'}
            if sacrifice_town == getattr(sacrifice_owner, 'base', None):
                return {'error': 'Base organization cannot be sacrificed'}
            targets = self._interactive_support_dissolve_targets_near_town(
                player,
                sacrifice_town,
                max_steps=int((context.get('effect_payload') or {}).get('range', 1) or 1),
                target_players=self._target_players_for_interaction(player, context.get('target_player_id')),
                target_region=(context.get('effect_payload') or {}).get('target_region'),
                excluded_target=(getattr(sacrifice_owner, 'id', None), sacrifice_town),
            )
            if not targets:
                return {'error': 'No enemy organization within range of sacrificed organization'}
            if card_name == '派遣間諜' and sacrifice_owner is not player:
                self._set_pending_option_choice(
                    sacrifice_owner,
                    'shared_spy_origin_consent',
                    ['不同意', '同意'],
                    f'{player.name} 想以你在 {sacrifice_town} 的組織發動派遣間諜，是否同意？',
                    source_name=card_name,
                    context={
                        'actor_player_id': player.id,
                        'owner_player_id': sacrifice_owner.id,
                        'sacrifice_town': sacrifice_town,
                        'flow_context': context,
                    },
                )
                return {'success': True, 'pending_choice': True, 'awaiting_consent': True}
            # Deferred to the final confirmation: no own organization is removed here. This is
            # only the town *pick* -- the actual sacrifice happens atomically together with the
            # enemy dissolve once the target step below is confirmed, so a cancel issued at any
            # point up to (and not including) that final confirmation is a true no-op.
            next_context = dict(context)
            next_context['sacrifice_town'] = sacrifice_town
            next_context['sacrifice_owner_player_id'] = getattr(sacrifice_owner, 'id', None)
            max_steps = int((context.get('effect_payload') or {}).get('range', 1) or 1)
            self._set_pending_support_flow_choice(
                player,
                'support_interaction',
                'target',
                f'{card_name}：選擇 {sacrifice_town} {max_steps} 格內的 1 個敵方組織瓦解。',
                source_name=card_name,
                targets=targets,
                context=next_context,
                **self._dissolve_cancel_kwargs(next_context),
            )
            return {'success': True, 'pending_choice': True, 'town': sacrifice_town}
        if effect_type in {'interactive_dissolve_many_near', 'interactive_dissolve_self_and_enemy', 'interactive_dissolve_and_build'}:
            raw_payload = context.get('effect_payload')
            payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
            max_steps = int(payload.get('range', 1) or 1)
            target_players = self._target_players_for_interaction(player, context.get('target_player_id'))
            target_region = payload.get('target_region')
            selected = result.get('selected') or {}
            target_player_id = selected.get('player_id')
            town = selected.get('town')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None or not town:
                return {'error': 'Invalid dissolve target'}
            if effect_type == 'interactive_dissolve_self_and_enemy':
                sacrifice_town = context.get('sacrifice_town')
                if not sacrifice_town:
                    return {'error': 'Missing sacrificed organization'}
                sacrifice_owner_player_id = context.get('sacrifice_owner_player_id')
                sacrifice_owner = (
                    next((p for p in self.players if getattr(p, 'id', None) == sacrifice_owner_player_id), None)
                    if sacrifice_owner_player_id is not None
                    else player
                )
                # The sacrifice was never applied to the board (deferred -- see the
                # 'sacrifice_town' branch above and `shared_spy_origin_consent`'s consent-granted
                # path), so it must still be re-validated as legal here, at the final
                # confirmation, exactly like any other stale-target check.
                if (
                    sacrifice_owner is None
                    or sacrifice_owner.organizations.get(sacrifice_town, 0) <= 0
                    or sacrifice_town == getattr(sacrifice_owner, 'base', None)
                ):
                    return {'error': 'Sacrificed organization is no longer valid'}
                current_targets = self._interactive_support_dissolve_targets_near_town(
                    player,
                    sacrifice_town,
                    max_steps=max_steps,
                    target_players=target_players,
                    target_region=target_region,
                )
                if not any(
                    entry.get('player_id') == target_player_id and entry.get('town') == town
                    for entry in current_targets
                ):
                    return {'error': 'Target organization is not within range of sacrificed organization'}
            else:
                current_targets = self._interactive_support_dissolve_targets(
                    player,
                    require_self_sacrifice=False,
                    max_steps=max_steps,
                    target_players=target_players,
                    target_region=target_region,
                    include_shared_source=bool(context.get('include_shared_source', False)),
                )
                target_still_legal = any(
                    entry.get('player_id') == target_player_id and entry.get('town') == town
                    for entry in current_targets
                )
                if not target_still_legal:
                    return {'error': 'Target organization is no longer within range'}
                if effect_type == 'interactive_dissolve_and_build' and not self._can_replace_dissolved_org_with_own(player, target_player, town):
                    return {'error': 'Target cannot be replaced with an organization'}

            total_count = int(payload.get('count', 1) or 1) if effect_type == 'interactive_dissolve_many_near' else 1
            if effect_type == 'interactive_dissolve_many_near' and total_count > 1:
                # Multi-target dissolve (e.g. 北國奧援 III): per requirement #6, only the FINAL
                # Confirm may commit anything atomically -- this pick is recorded without
                # touching the board yet, so a cancel issued after any non-final pick is still a
                # true no-op. The accumulated picks are re-validated and applied together, one
                # `dissolve_organization()` call each, only once the count is filled (or no
                # further legal target remains).
                accumulated_picks = list(context.get('accumulated_dissolve_picks') or [])
                accumulated_picks = accumulated_picks + [{'target_player_id': target_player_id, 'town': town}]
                remaining_count = total_count - len(accumulated_picks)
                if remaining_count > 0:
                    next_targets = [
                        entry for entry in self._interactive_support_dissolve_targets(
                            player,
                            require_self_sacrifice=False,
                            max_steps=max_steps,
                            target_players=target_players,
                            target_region=target_region,
                            include_shared_source=bool(context.get('include_shared_source', False)),
                        )
                        if not any(
                            pick['target_player_id'] == entry.get('player_id') and pick['town'] == entry.get('town')
                            for pick in accumulated_picks
                        )
                    ]
                    if next_targets:
                        next_context = {**context, 'accumulated_dissolve_picks': accumulated_picks, 'remaining_count': remaining_count}
                        self._set_pending_support_flow_choice(
                            player,
                            'support_interaction',
                            'target',
                            f'{card_name}：已選 {len(accumulated_picks)}/{total_count}，還可再選 {remaining_count} 個鄰近敵方組織。',
                            source_name=card_name,
                            targets=next_targets,
                            remaining_count=remaining_count,
                            selected_count=len(accumulated_picks),
                            total_count=total_count,
                            context=next_context,
                            **self._dissolve_cancel_kwargs(next_context),
                        )
                        self.log(f"{player.name} selected one {card_name} target ({len(accumulated_picks)}/{total_count}); not yet dissolved")
                        return {
                            'success': True,
                            'pending_choice': True,
                            'selected_count': len(accumulated_picks),
                            'total_count': total_count,
                            'remaining_count': remaining_count,
                        }
                    self.log(f"{player.name} has {remaining_count} {card_name} dissolve(s) remaining but no further legal target; confirming {len(accumulated_picks)} now")
                # Final confirmation: re-validate every accumulated pick against the live board
                # BEFORE applying anything (req #9 -- an earlier pick could have gone stale while
                # later picks were still being made). This must be all-or-nothing (req #6): a
                # stale pick may NOT be silently dropped while the remaining (now-partial) picks
                # still get dissolved and the card still gets consumed -- that would resolve a
                # 2-target pick into only 1 actual dissolution. So the board is only ever mutated
                # below once EVERY accumulated pick has independently confirmed still-legal;
                # otherwise nothing is applied, nothing is consumed, and the flow either re-opens
                # onto a fresh legal target for the vacated slot(s) or fully fizzles -- mirroring
                # the same all-or-nothing discipline already used for the two-phase
                # self-sacrifice flows' own stale-target revalidation above. (Parent-level
                # review, defect 2.)
                live_targets_for_validation = self._interactive_support_dissolve_targets(
                    player,
                    require_self_sacrifice=False,
                    max_steps=max_steps,
                    target_players=target_players,
                    target_region=target_region,
                    include_shared_source=bool(context.get('include_shared_source', False)),
                )
                still_valid_picks = [
                    pick for pick in accumulated_picks
                    if any(
                        entry.get('player_id') == pick['target_player_id'] and entry.get('town') == pick['town']
                        for entry in live_targets_for_validation
                    )
                ]
                if len(still_valid_picks) < len(accumulated_picks):
                    stale_towns = [
                        pick['town'] for pick in accumulated_picks if pick not in still_valid_picks
                    ]
                    remaining_count = total_count - len(still_valid_picks)
                    next_targets = [
                        entry for entry in live_targets_for_validation
                        if not any(
                            pick['target_player_id'] == entry.get('player_id') and pick['town'] == entry.get('town')
                            for pick in still_valid_picks
                        )
                    ]
                    if remaining_count > 0 and next_targets:
                        next_context = {
                            **context,
                            'accumulated_dissolve_picks': still_valid_picks,
                            'remaining_count': remaining_count,
                        }
                        self._set_pending_support_flow_choice(
                            player,
                            'support_interaction',
                            'target',
                            f'{card_name}：{"、".join(stale_towns)} 已不再是合法目標，請重新選擇 {remaining_count} 個鄰近敵方組織。',
                            source_name=card_name,
                            targets=next_targets,
                            remaining_count=remaining_count,
                            selected_count=len(still_valid_picks),
                            total_count=total_count,
                            context=next_context,
                            **self._dissolve_cancel_kwargs(next_context),
                        )
                        self.log(f"{player.name}'s {card_name} pick(s) at {'、'.join(stale_towns)} became illegal before final confirmation; re-opened for {remaining_count} more")
                        return {
                            'success': True,
                            'pending_choice': True,
                            'retryable': True,
                            'selected_count': len(still_valid_picks),
                            'total_count': total_count,
                            'remaining_count': remaining_count,
                            'stale_towns': stale_towns,
                        }
                    # No legal replacement target exists at all -- nothing can be applied or
                    # re-picked, so the whole flow fizzles: card already committed (per the
                    # existing on-play cost semantics this feature never changed), but zero
                    # board effect, exactly like the fizzle already used when no legal target
                    # remained after an earlier non-final pick above.
                    choice['is_final_confirmation'] = True
                    self.pending_choice = None
                    self.log(f"{player.name}'s {card_name} confirmation had stale target(s) at {'、'.join(stale_towns)} with no legal replacement; effect fizzled")
                    return {'success': True, 'effect_fizzled': True, 'reason': 'Stale target', 'source_name': card_name}

                # Every accumulated pick is still legal -- apply them all atomically.
                applied = []
                for pick in accumulated_picks:
                    pick_target_player = next((p for p in self.players if getattr(p, 'id', None) == pick['target_player_id']), None)
                    if pick_target_player is None:
                        continue
                    pick_result = self.dissolve_organization(
                        player, pick_target_player, pick['town'], source='support_card', _from_pending_choice=True
                    )
                    if not pick_result.get('error'):
                        applied.append({'town': pick['town'], 'target_player_id': pick['target_player_id']})
                # As above: this IS the atomic final-confirmation commit for the whole
                # multi-target flow (every accumulated pick just got dissolved above), regardless
                # of how many earlier picks were queued/parked elsewhere along the way.
                choice['is_final_confirmation'] = True
                self.pending_choice = None
                self.log(f"{player.name} resolved {card_name}: dissolved {len(applied)} organization(s)")
                return {'success': True, 'dissolved': applied, 'target_count': len(applied)}

            # Single-target dissolve (interactive_dissolve_many_near with total_count == 1),
            # interactive_dissolve_self_and_enemy, and interactive_dissolve_and_build: exactly
            # one target is chosen and this resolver call already *is* the flow's only/final
            # confirmation, so it commits immediately with no deferred-accumulation bookkeeping.
            dissolve_result = self.dissolve_organization(
                player, target_player, town, source='support_card', _from_pending_choice=True
            )
            if dissolve_result.get('error'):
                return dissolve_result
            # This resolve call is committing real board state right now -- tag the JUST-RESOLVED
            # choice object itself (not wherever a paused choice might currently be parked: that
            # can be self.pending_choice, a queued continuation, or the single deferred-build
            # slot, and is not reliably enumerable) so `_settle_deferred_card_play_triggers`
            # (resolve_pending_choice's tail) knows unambiguously that any deferred
            # post_play_faction_triggers on this flow may now fire.
            choice['is_final_confirmation'] = True
            if effect_type == 'interactive_dissolve_self_and_enemy':
                # Apply the deferred sacrifice now, atomically alongside the enemy dissolve above
                # -- this single resolver call is the flow's one and only final confirmation, so
                # by construction no own organization existed in a removed state at any point a
                # cancel could have been issued.
                sacrifice_owner.organizations[sacrifice_town] -= 1
                if sacrifice_owner.organizations[sacrifice_town] <= 0:
                    del sacrifice_owner.organizations[sacrifice_town]
                shared_text = f"（實體屬於{sacrifice_owner.name}）" if sacrifice_owner is not player else ''
                self.log(f"{player.name} dissolved 1 own organization at {sacrifice_town}{shared_text} for {card_name}")
            if effect_type == 'interactive_dissolve_and_build':
                if not self._can_player_build_in_town(player, town):
                    if dissolve_result.get('red_base_hit') and not dissolve_result.get('red_base_destroyed'):
                        self.log(f"{player.name} resolved {card_name}: {town}紅軍根據地僅完成第 1 次瓦解命中，組織尚未移除，故不建立")
                        return {
                            'success': True,
                            'town': town,
                            'target_player_id': target_player_id,
                            'red_base_hit': True,
                            'red_base_destroyed': False,
                            'built': False,
                        }
                    return {'error': 'Target could not be replaced after dissolve'}
                self._place_organization(player, town)
                self._record_action_build(player, town)
                self.log(f"{player.name} resolved {card_name} and built in {town} after dissolve")
                return {
                    'success': True,
                    'town': town,
                    'target_player_id': target_player_id,
                    'red_base_hit': bool(dissolve_result.get('red_base_hit')),
                    'red_base_destroyed': bool(dissolve_result.get('red_base_destroyed')),
                    'built': True,
                }
            return {'success': True, 'town': town, 'target_player_id': target_player_id}
        if effect_type == 'force_discard_near':
            selected = result.get('selected') or {}
            target_player_id = selected.get('player_id') or selected.get('id')
            target_player = next((p for p in self.players if getattr(p, 'id', None) == target_player_id), None)
            if target_player is None:
                return {'error': 'Invalid discard target'}
            if not getattr(target_player, 'hand', None):
                return {'error': 'Target player has no hand cards'}
            payload = context.get('effect_payload') or {}
            if not self._player_has_org_within_steps_of_player(
                player,
                target_player,
                max_steps=int(payload.get('range', 1) or 1),
                target_region=payload.get('target_region'),
                include_shared_source=bool(context.get('include_shared_source', False)),
            ):
                return {'error': 'Target player is not within range'}
            # This resolve is committing (the target player is now locked in, whether the
            # ensuing discard is random -- immediate -- or a choice handed to the target player,
            # whose own follow-up choice never carries this marker forward; matches this
            # pre-existing flow's original, unchanged timing). See
            # _settle_deferred_card_play_triggers for why this is tagged on the choice itself.
            choice['is_final_confirmation'] = True
            count = int(payload.get('count', 0) or 0)
            random_pick = bool(payload.get('random'))
            if random_pick:
                discarded_names = []
                for _ in range(min(count, len(target_player.hand))):
                    idx = random.randrange(len(target_player.hand))
                    discarded = target_player.hand.pop(idx)
                    discarded_names.append(getattr(discarded, 'name', str(discarded)))
                    target_player.deck.discard([discarded])
                self.log(f"{player.name} resolved {card_name} targeting {target_player.name} and discarded {len(discarded_names)} random card(s)")
                return {
                    'success': True,
                    'target_player_id': target_player_id,
                    'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                    'discarded_cards': discarded_names,
                }
            self.pending_choice = {
                'type': 'card_choice',
                'choice_key': 'tianfang_support_target_discard',
                'player_id': target_player.id,
                'cards': list(target_player.hand),
                'prompt': f"{card_name}：請選擇 1 張手牌棄掉。",
                'source_name': card_name,
                'context': {
                    'initiator_player_id': player.id,
                    'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                    'target_player_id': target_player.id,
                    'target_player_name': getattr(target_player, 'name', str(target_player_id)),
                    **context,
                },
            }
            return {
                'success': True,
                'pending_choice': True,
                'target_player_id': target_player_id,
                'target_player_name': getattr(target_player, 'name', str(target_player_id)),
            }
        return {'error': 'Unsupported support interaction result'}

    def _resolve_red_support_target_choice(self, player, card):
        # 只有行動模式會走到這裡（資源模式 2026-08-08 起直接取得資源、卡片入自己棄牌堆，
        # 不再問要放進誰的棄牌堆，見 play_card 的資源模式分支）。
        current_faction = self.faction_by_id.get(player.faction_id, {})
        current_camp = current_faction.get('camp')
        if current_camp != 'red_army':
            return None
        targets = [
            {'id': getattr(other, 'id', None), 'label': getattr(other, 'name', str(getattr(other, 'id', '')))}
            for other in self.players
            if other is not player and self.faction_by_id.get(other.faction_id, {}).get('camp') != 'red_army'
        ]
        if not targets:
            return None
        self._set_pending_target_choice(
            player,
            'red_support_target_player',
            targets,
            '紅軍奧援：請選擇要將本牌放入哪位反共玩家的棄牌堆。',
            source_name='紅軍奧援',
            context={
                'card_name': '紅軍奧援',
                'card': card,
            },
        )
        return {'pending_choice': True, 'card_moved_out_of_play': True}

    def _reaction_card_cancel_predicate(self, reaction_card_name, canceled_cost):
        # 2026-08-05 使用者回報：打出宣傳家（購買費用只有宣傳、無資金）時，產業滲透完全
        # 不會被列為候選反應卡。根因：這裡曾經把「產業滲透能不能取消這張牌」本身也綁在
        # 「被取消的牌購買費用有資金」上，但卡面原文（data/raw/action_cards.csv）是「其他
        # 玩家行動時打出，取消1張對方所打出行動卡之能力。若被取消的牌購買費用有資金，
        # 抽1張牌」——能不能取消是無條件的，資金費用只決定「取消後有沒有 bonus 抽牌」；
        # 爆料黑幕（依宣傳費用給 bonus 抽牌）與情報網都已經是無條件可取消，產業滲透應該
        # 對稱，三張反應卡因此統一無條件可取消；bonus 抽牌的費用條件維持在
        # `_apply_reaction_cancel_flags`/`_build_reaction_context` 另外判斷，不受影響。
        return reaction_card_name in {'爆料黑幕', '產業滲透', '情報網'}

    def _reaction_prompt_candidates(self, acting_player, played_card, include_support=False):
        # 奧援卡是 support card. Historically we returned no candidates for support cards
        # because their effect resolved eagerly inside play_card, so offering a late
        # cancel prompt left a stale pending_choice that blocked phase advance. Support
        # plays now defer their board effect until *after* the reaction window closes
        # (see play_card's support branch and _resume_reaction_pending_action), so the
        # deferred-support path passes include_support=True to get real candidates while
        # every other caller keeps the safe no-support default.
        if not include_support and getattr(played_card, 'card_type', None) == 'support':
            return []
        cost = self._card_purchase_cost(played_card) or {}
        candidates = []
        for player in self.players:
            if player is acting_player:
                continue
            cards = []
            for hand_index, hand_card in enumerate(getattr(player, 'hand', []) or []):
                name = getattr(hand_card, 'name', str(hand_card))
                if name not in {'爆料黑幕', '產業滲透', '情報網'}:
                    continue
                if not self._reaction_card_cancel_predicate(name, cost):
                    continue
                cards.append({'name': name, 'card_index': hand_index})
            if cards:
                candidates.append({'player': player, 'cards': cards})
        return candidates

    def _commit_support_card_play(self, player, played_card, card_name, action_context):
        # Resolve a support card's board effect after its cancel-reaction window has
        # closed without a cancellation. Shared by play_card (no eligible reactor) and
        # _resume_reaction_pending_action (reactor declined). Returns a response dict when
        # the play must stop here (the support card opened its own interactive pending
        # choice), or None to let the caller run the shared post-play tail (faction
        # ability triggers + discard), mirroring the non-interactive support path.
        support_resolution = self._execute_support_card(player, played_card)
        action_context['support_resolution'] = support_resolution
        if support_resolution and support_resolution.get('card_moved_out_of_play'):
            action_context['removed_current_card'] = True
        if support_resolution and support_resolution.get('pending_choice'):
            pending_destination = (
                self._queued_card_build_choices[-1]
                if support_resolution.get('queued_map_choice') and self._queued_card_build_choices
                else self.pending_choice
            )
            pending_context = pending_destination.setdefault('context', {}) if pending_destination else {}
            pending_context['post_play_faction_triggers'] = {
                'player_id': player.id,
                'cost_has_money': bool(action_context.get('cost_has_money')),
                'cost_has_propaganda': bool(action_context.get('cost_has_propaganda')),
                'played_card': played_card,
                'used_faction_ability_names': list(action_context.get('used_faction_ability_names') or []),
            }
            pending_effect_type = pending_context.get('effect_type')
            if (
                pending_destination is not None
                and action_context.get('hand_index') is not None
                and pending_effect_type in DISSOLVE_INTERACTIVE_EFFECT_TYPES
            ):
                # No dissolve-card/support-tier effect in DISSOLVE_INTERACTIVE_EFFECT_TYPES has
                # mutated the board at the initial target/sacrifice choice (support cards other
                # than 北國奧援/臺灣奧援's dissolve tiers -- e.g. build/discard interactions --
                # never opt into this), so this first step can still be cancelled as an atomic
                # card play (the player's own rollback, distinct from the opponent's reaction).
                # Seeding the snapshot into `pending_context` (not just onto `pending_destination`
                # itself) lets it survive being copied forward into every later stage of the flow
                # (`next_context = dict(context)` / `{**context, ...}`, see
                # `_resolve_support_interaction_result`), so `_dissolve_cancel_kwargs()` can
                # re-derive the same rollback_* kwargs at every subsequent stage transition too.
                # NOTE: play_card() always seeds action_context['_dissolve_cancel_snapshot']
                # unconditionally before any branch runs, so the `or {...}` fallback below is
                # unreachable in practice; kept (and kept in sync with the same
                # contributed_*-based schema -- see play_card's own snapshot construction) only
                # as defense-in-depth against a future caller of this method that doesn't.
                pending_context['_dissolve_cancel_snapshot'] = action_context.get('_dissolve_cancel_snapshot') or {
                    'card': played_card,
                    'hand_index': action_context.get('hand_index'),
                    'contributed_money_cost': bool(action_context.get('cost_has_money')),
                    'contributed_propaganda_cost': bool(action_context.get('cost_has_propaganda')),
                    'contributed_nonstarter_name': card_name,
                    'borrowed_owner_id': action_context.get('borrowed_owner_id'),
                    'borrowed_purchase_area_index': action_context.get('borrowed_purchase_area_index'),
                    'event_progress': action_context.get('prior_event_progress'),
                    'event_notification': action_context.get('prior_event_notification'),
                    'event_progress_after': (
                        dict(self.event_progress) if isinstance(self.event_progress, dict) else self.event_progress
                    ),
                }
                pending_destination.update(self._dissolve_cancel_kwargs(pending_context))
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            return {"success": True, "pending_choice": True, **support_resolution}
        return None

    def _commit_red_support_card_play(self, player, played_card, card_name):
        # 2026-08-05 使用者回報：打出紅軍奧援時，對手的爆料黑幕/產業滲透/情報網完全不會
        # 跳出取消詢問——紅軍奧援有自己一套獨立於一般奧援卡（_execute_support_card）的
        # 結算邏輯（_resolve_red_support_target_choice 決定要不要問「放進哪位反共玩家的
        # 棄牌堆」），過去整段直接寫死在 play_card() 裡、從未檢查過反應候選。這裡把「真正
        # 結算紅軍奧援」抽成獨立函式，讓 play_card 與 _resume_reaction_pending_action 共用，
        # 比照一般奧援卡在 9e2c6e9 已經做過的「先開反應視窗、再結算效果」延後模式。
        self._draw_player_cards(player, 1, trigger_name='紅軍奧援')
        support_resolution = self._resolve_red_support_target_choice(player, played_card)
        if support_resolution and support_resolution.get('pending_choice'):
            self.log(f"{player.name} played {card_name}")
            return {"success": True, **support_resolution}
        # 紅軍奧援是紅軍專屬卡：非紅軍陣營（借用/取得後）打出，結算後應回到
        # 紅軍玩家的棄牌堆，不留在自己的棄牌堆（P1 playtest 回報）
        current_camp = self.faction_by_id.get(player.faction_id, {}).get('camp')
        red = self._red_player()
        if current_camp != 'red_army' and red is not None and red is not player:
            red.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}; card returned to {red.name}'s discard pile")
            return {"success": True, "card_returned_to": red.name}
        player.deck.discard([played_card])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def _resume_reaction_pending_action(self, choice, reaction_context=None, skip_reaction_resolution=False):
        # skip_reaction_resolution: when a multi-layer counter-cancel chain resolves via
        # _finalize_reaction_stack, that walker already resolves every reaction card's own
        # effect (bonus draw / discard). In that case reaction_context is still passed to
        # signal "the original play was canceled" (so it is NOT executed), but the direct
        # canceller's reaction card must NOT be re-resolved here — the walker did it. The
        # default (False) preserves the legacy single-cancellation path exactly.
        player = choice.get('acting_player')
        played_card = choice.get('played_card')
        card_name = choice.get('played_card_name')
        effective_type = choice.get('effective_type')
        action_context = dict(choice.get('action_context') or {})
        red_army_action_name = action_context.get('red_army_action_name')
        if red_army_action_name:
            if reaction_context is not None:
                if not skip_reaction_resolution:
                    self._resolve_reaction_context(reaction_context)
                # 2026-08-06 使用者回報：用產業滲透/爆料黑幕取消紅軍能力後，該次能力額度
                # 完全沒有被標記為已使用——紅軍可以在同一回合對同一目標再試一次，等於白白
                # 浪費對手一張反應卡也擋不住。比照本次會話對「打出卡牌」的既有結論（出牌/
                # 發動能力這個動作本身就算數，之後被取消不會撤銷額度），取消時仍要呼叫
                # `_mark_red_army_action_used()`。
                red_kwargs = dict(action_context.get('red_army_action_kwargs') or {})
                self._mark_red_army_action_used(red_army_action_name, red_kwargs.get('target_player_id'))
                self.log(f"{player.name}'s {red_army_action_name} was canceled by reaction")
                return {"success": True, "canceled": True}
            red_kwargs = dict(action_context.get('red_army_action_kwargs') or {})
            red_kwargs['_skip_reaction_prompt'] = True
            return self._activated_faction_action(player, red_army_action_name, **red_kwargs)
        if action_context.get('is_red_support_card'):
            if reaction_context is not None:
                if not skip_reaction_resolution:
                    self._resolve_reaction_context(reaction_context)
                # 比照一般奧援卡被取消時的處理：不執行紅軍奧援的效果，只把卡牌放到正確的
                # 棄牌堆（非紅軍玩家手上的紅軍奧援結算後一律歸還紅軍棄牌堆，紅軍自己打出
                # 則留在自己棄牌堆），與 _commit_red_support_card_play 未被取消時的歸位規則一致。
                current_camp = self.faction_by_id.get(player.faction_id, {}).get('camp')
                red = self._red_player()
                if current_camp != 'red_army' and red is not None and red is not player:
                    red.deck.discard([played_card])
                    self.log(f"{player.name}'s {card_name} was canceled by reaction; card returned to {red.name}'s discard pile")
                else:
                    player.deck.discard([played_card])
                    self.log(f"{player.name}'s {card_name} was canceled by reaction")
                return {"success": True, "canceled": True}
            return self._commit_red_support_card_play(player, played_card, card_name)
        action_context['current_card'] = played_card
        action_context['card_name'] = card_name
        support_resolution = choice.get('support_resolution')

        if reaction_context is not None:
            action_context['reaction_context'] = reaction_context
            action_context['card_canceled'] = True

        if effective_type == 'support':
            if action_context.get('card_canceled'):
                # An opponent used a reaction card to cancel this support play: resolve
                # the reaction (its own effect + discard), discard the canceled support
                # card, and do NOT run the support card's board effect.
                if not skip_reaction_resolution:
                    self._resolve_reaction_context(reaction_context)
                if not action_context.get('removed_current_card'):
                    if not self._return_borrowed_card_to_owner_topdeck(played_card):
                        player.deck.discard([played_card])
                self.log(f"{player.name}'s {card_name} was canceled by reaction")
                return {"success": True, "canceled": True}
            # Not canceled: resolve the deferred support effect now. If it opens its own
            # interactive pending choice, stop here; otherwise fall through to the shared
            # tail (reaction_context is None, so faction ability triggers + discard run
            # exactly as on the immediate no-reactor support play path).
            support_response = self._commit_support_card_play(player, played_card, card_name, action_context)
            if support_response is not None:
                return support_response

        if effective_type != 'support':
            if card_name in {"派遣間諜", "內應間諜"}:
                # A declined reaction resumes the same committed card play -- but 派遣間諜/
                # 內應間諜 have NO `effect` entry in action_engine.cards (their dissolve
                # mechanic is hardcoded via _start_card_dissolve_interaction, not the generic
                # data-driven effect pipeline the `elif` branch below drives). Routing them
                # through that generic branch instead does nothing: the `elif` condition is
                # simply false for these two cards, so control fell through to the shared tail
                # below, discarded the card, fired cost/faction-ability hooks, and never opened
                # a target choice at all -- the player lost the card for nothing. Mirror
                # play_card's own direct-play special-case for these two cards exactly (see
                # that branch, above in play_card itself) so the cancellable dissolve flow opens
                # here exactly as it would on a normal, non-reaction-interrupted play.
                # (Parent-level review, defect 3.)
                if not action_context.get('card_canceled'):
                    spy_result = self._start_card_dissolve_interaction(
                        player,
                        card_name,
                        requires_self_sacrifice=(card_name == "派遣間諜"),
                        range_limit=self._event_card_range_context(player, played_card)['range_limit'],
                        target_player_id=action_context.get('target_player_id'),
                        target_region=self._event_card_range_context(player, played_card)['target_region'],
                        extra_context={
                            **(
                                {'era_followup_discard_choice': action_context.get('era_followup_discard_choice')}
                                if action_context.get('era_followup_discard_choice') else {}
                            ),
                            '_dissolve_cancel_snapshot': action_context.get('_dissolve_cancel_snapshot'),
                            'post_play_faction_triggers': {
                                'player_id': player.id,
                                'cost_has_money': bool(action_context.get('cost_has_money')),
                                'cost_has_propaganda': bool(action_context.get('cost_has_propaganda')),
                                'played_card': played_card,
                                'used_faction_ability_names': list(action_context.get('used_faction_ability_names') or []),
                            },
                        },
                    )
                    if spy_result and spy_result.get('pending_choice'):
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True, **spy_result}
                    return {"error": "No target organization within range"}
            elif card_name in getattr(self.action_engine, 'cards', {}):
                if not action_context.get('card_canceled'):
                    action_result = self.action_engine.execute(card_name, player, self, context=action_context, include_resources=False)
                    if isinstance(action_result, dict) and action_result.get('pending_choice'):
                        # A declined reaction resumes the same committed card play, but this
                        # branch used to return before the shared purchase-cost faction
                        # triggers below. Mirror the direct path for every command/
                        # organization card that continues through a pending choice.
                        self._apply_era_play_card_effects(player, played_card)
                        self._apply_card_play_faction_abilities(
                            player,
                            cost_has_money=bool(action_context.get('cost_has_money')),
                            cost_has_propaganda=bool(action_context.get('cost_has_propaganda')),
                            played_card=played_card,
                            used_faction_ability_names=action_context.get('used_faction_ability_names'),
                        )
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True}

        if action_context.get('card_canceled'):
            # 2026-09-06 使用者回報：一般指令/組織卡（非奧援、非紅軍特殊行動）被取消反應
            # 卡取消後，落到跟「正常出牌成功」共用的結尾程式碼，補寫一筆「played {card}」
            # 紀錄、回傳值也跟成功出牌一樣分不出差別，玩家看紀錄／收到的結果訊息都以為
            # 這張卡打成功了。比照上面奧援卡、紅軍特殊行動被取消時已有的處理，提早結束、
            # 記錄成「被取消」，不要落進下面共用的成功結尾。
            if not skip_reaction_resolution:
                self._resolve_reaction_context(reaction_context)
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name}'s {card_name} was canceled by reaction")
            return {"success": True, "canceled": True}

        if not skip_reaction_resolution:
            self._resolve_reaction_context(reaction_context)

        if self.pending_choice and card_name == '情報網':
            # 情報網's `choose_one` always ends up open here (mirrors play_card's own shared
            # tail -- see that special-case for the full rationale: effect_engine.py's
            # `choose_one` handler doesn't return a `pending_choice` dict for
            # action_engine.execute to catch above, so it always falls through to this generic
            # tail). Unlike every OTHER card_name reaching this point, 情報網's cost/nonstarter
            # contribution was ALREADY noted by play_card's own eager _note_* calls -- those run
            # BEFORE 情報網's reaction-candidate check (unlike 紅軍奧援/is_red_support_card/
            # general 奧援卡, which check for an eligible reactor before their own note-calls and
            # so, when deferred here, never noted at all -- that's what the comment below this
            # branch is about). Re-noting here would double-count this play's own contribution
            # (a real regression this feature's ref-counted turn_log tracking would otherwise
            # turn into a *permanently* stuck True flag, since the matching single cancel-time
            # decrement could never catch up to a double-increment). Defer to
            # `_settle_deferred_card_play_triggers` instead -- exactly like play_card's tail --
            # and do NOT call the _note_* helpers again.
            self.pending_choice.setdefault('context', {})['post_play_faction_triggers'] = {
                'player_id': player.id,
                'cost_has_money': bool(action_context.get('cost_has_money')),
                'cost_has_propaganda': bool(action_context.get('cost_has_propaganda')),
                'played_card': played_card,
                'used_faction_ability_names': list(action_context.get('used_faction_ability_names') or []),
            }
        else:
            # Deferred-reaction path never used to set these (only the immediate play_card
            # path did), so a card that triggered a reaction prompt — even one the reactor
            # skipped — silently failed to count toward 點燃熱情/樹立信心's "played a card with
            # money/propaganda cost this turn" condition for whichever card came after it.
            if action_context.get('cost_has_money'):
                self._note_money_cost_card_played()
            if action_context.get('cost_has_propaganda'):
                self._note_propaganda_cost_card_played()

            trigger_cost_has_money = action_context.get('cost_has_money')
            trigger_cost_has_propaganda = action_context.get('cost_has_propaganda')
            self._apply_card_play_faction_abilities(
                player,
                cost_has_money=bool(trigger_cost_has_money),
                cost_has_propaganda=bool(trigger_cost_has_propaganda),
                played_card=played_card,
                used_faction_ability_names=action_context.get('used_faction_ability_names'),
            )

        if self.pending_choice:
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            return {"success": True, "pending_choice": True}

        if not action_context.get('removed_current_card'):
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def _set_pending_reaction_choice(
        self,
        reacting_player,
        acting_player,
        played_card,
        card_name,
        candidates,
        effective_type,
        action_context,
        support_resolution=None,
        remaining_candidates=None,
        resolution_stack=None,
        closed_reactor_ids=None,
    ):
        # 2026-08-02 使用者更正：只要持有卡牌，對手「每一次」符合條件的行動都要問是否取消，
        # 不是「這回合問過這個人一次就不再問」。因此這裡不再記錄／檢查 per-turn 的
        # 已詢問名單；`remaining_candidates` 改為承載「這一次出牌」還沒問過的其他候選人，
        # 供 `_resolve_reaction_choice` 在目前這位玩家選擇不取消時，接著問下一位候選人
        # ——而不是問過第一位就直接讓行動結算。
        #
        # 2026-08-05 反制鏈（counter-cancel）：`resolution_stack` 承載「這條取消鏈」由下往上
        # 的每一層 frame——stack[0] 是最初的出牌（kind='original'），stack[k>=1] 是第 k 次
        # 打出的反應卡（kind='reaction'）。第一層（對最初出牌的反應）由本函式自動建立
        # stack=[original_frame]；更深層由 `_resolve_reaction_choice` 取消分支 push 反應 frame
        # 後帶入。任何一層的候選池全部謝絕時，`_finalize_reaction_stack` 依交替規則一次結算。
        if resolution_stack is None:
            resolution_stack = [{
                'kind': 'original',
                'choice': {
                    'acting_player': acting_player,
                    'played_card': played_card,
                    'played_card_name': card_name,
                    'effective_type': effective_type,
                    'action_context': dict(action_context or {}),
                    'support_resolution': support_resolution,
                },
            }]
        self.pending_choice = {
            'type': 'reaction_choice',
            'choice_key': 'cancel_other_player_action',
            'player_id': reacting_player.id,
            'player_name': reacting_player.name,
            'acting_player': acting_player,
            'acting_player_id': acting_player.id,
            'acting_player_name': acting_player.name,
            'played_card': played_card,
            'played_card_name': card_name,
            'effective_type': effective_type,
            'action_context': dict(action_context or {}),
            'support_resolution': support_resolution,
            'cards': list(candidates),
            'remaining_candidates': list(remaining_candidates or []),
            'resolution_stack': resolution_stack,
            # If one player accepted a reaction, every still-waiting responder in that
            # layer has had the same prompt closed. Keep those player ids out of deeper
            # counter layers so the dismissed prompt cannot immediately reappear.
            'closed_reactor_ids': sorted(closed_reactor_ids or []),
            'prompt': f'{acting_player.name} 打出 {card_name}。是否要取消對方的行動？',
            'source_name': '取消反應',
        }
        self.log(f"{acting_player.name} played {card_name}; waiting up to 10 seconds for {reacting_player.name} to choose cancel reaction")
        return {'pending_choice': True}

    def _resolve_reaction_choice(self, player, choice, index):
        cards = choice.get('cards') or []
        if index is None:
            return {'error': 'Invalid choice index'}
        resolution_stack = list(choice.get('resolution_stack') or [])
        if index == 0:
            # Decline at this layer. The flat `remaining_candidates` chain is orthogonal to
            # the counter-cancel stack: first hand this layer's card to any other eligible
            # candidate; only when the whole candidate pool of THIS layer declines is the
            # current top card left uncanceled → walk the stack and settle every layer.
            remaining = list(choice.get('remaining_candidates') or [])
            if remaining:
                next_candidate = remaining[0]
                self.pending_choice = None
                result = self._set_pending_reaction_choice(
                    next_candidate['player'],
                    choice.get('acting_player'),
                    choice.get('played_card'),
                    choice.get('played_card_name'),
                    next_candidate['cards'],
                    choice.get('effective_type'),
                    choice.get('action_context'),
                    support_resolution=choice.get('support_resolution'),
                    remaining_candidates=remaining[1:],
                    resolution_stack=resolution_stack,
                    closed_reactor_ids=choice.get('closed_reactor_ids'),
                )
                result['success'] = True
                result['skipped_reaction'] = True
                result['next_reactor_id'] = next_candidate['player'].id
                return result
            self.pending_choice = None
            result = self._finalize_reaction_stack(resolution_stack)
            result['skipped_reaction'] = True
            return result
        card_choice_index = index - 1
        if card_choice_index < 0 or card_choice_index >= len(cards):
            return {'error': 'Invalid choice index'}
        selected = cards[card_choice_index]
        reaction_context = self._build_reaction_context(
            choice.get('acting_player'),
            choice.get('played_card'),
            choice.get('played_card_name'),
            'action',
            {'player_id': player.id, 'card_index': selected.get('card_index')},
        )
        if reaction_context is None:
            return {'error': 'Invalid reaction card'}
        # This reactor cancelled the current top card by playing their own reaction card.
        # Close every still-waiting prompt in this layer before opening a counter layer.
        # The original actor and players from earlier completed layers may counter-cancel,
        # but responders whose sibling prompt was just closed cannot immediately receive
        # the same reaction prompt again in this chain.
        resolution_stack.append({'kind': 'reaction', 'reaction_context': reaction_context})
        self.pending_choice = None
        reaction_card = reaction_context['reaction_card']
        reaction_card_name = reaction_context['reaction_card_name']
        closed_reactor_ids = set(choice.get('closed_reactor_ids') or [])
        closed_reactor_ids.update(
            getattr(candidate.get('player'), 'id', None)
            for candidate in (choice.get('remaining_candidates') or [])
        )
        closed_reactor_ids.discard(None)
        counter_candidates = [
            candidate
            for candidate in self._reaction_prompt_candidates(player, reaction_card)
            if getattr(candidate.get('player'), 'id', None) not in closed_reactor_ids
        ]
        if counter_candidates:
            first = counter_candidates[0]
            result = self._set_pending_reaction_choice(
                first['player'],
                player,
                reaction_card,
                reaction_card_name,
                first['cards'],
                getattr(reaction_card, 'card_type', None),
                {},
                support_resolution=None,
                remaining_candidates=counter_candidates[1:],
                resolution_stack=resolution_stack,
                closed_reactor_ids=closed_reactor_ids,
            )
            result['success'] = True
            result['opened_counter_layer'] = True
        else:
            result = self._finalize_reaction_stack(resolution_stack)
        result['reaction_card'] = reaction_card_name
        result['canceled_card'] = reaction_context.get('canceled_card_name')
        return result

    def _apply_reaction_cancel_flags(self, reaction_context):
        # Set the bonus-draw turn_log flags for ONE reaction card, based on the printed cost
        # of the exact card it directly cancels. In a multi-layer chain each layer targets a
        # different card, so these flags must be (re)set per frame right before that frame's
        # reaction card resolves — the value the flag held when the context was first built
        # (possibly overwritten by a deeper layer) is not authoritative. Mirrors the flag
        # logic in _build_reaction_context so the single-cancellation path is unchanged.
        cost = reaction_context.get('canceled_card_cost') or {}
        name = reaction_context.get('reaction_card_name')
        if name == '爆料黑幕':
            self.turn_log['canceled_propaganda_card'] = int(cost.get('propaganda', 0) or 0) > 0
        elif name == '產業滲透':
            self.turn_log['canceled_money_cost_card'] = int(cost.get('money', 0) or 0) > 0

    def _discard_consumed_reaction_card(self, reaction_context):
        # A reaction card that was itself cancelled by a counter-cancel above it is still
        # consumed (already popped from hand in _build_reaction_context) but produces NO
        # effect and NO bonus draw — just move it to discard (or back to its owner's topdeck
        # if borrowed), mirroring _resolve_reaction_context's discard tail without the effect.
        card = reaction_context.get('reaction_card')
        reactor = reaction_context.get('reacting_player')
        if card is None or reactor is None:
            return
        if not self._return_borrowed_card_to_owner_topdeck(card):
            if card not in reactor.deck.discard_pile:
                reactor.deck.discard([card])
        self.log(f"{reactor.name}'s {reaction_context.get('reaction_card_name')} was itself canceled by a counter-reaction")

    def _finalize_reaction_stack(self, resolution_stack):
        # Settle a completed counter-cancel chain. `resolution_stack` is bottom-to-top:
        #   stack[0]  = the original card play              (kind='original')
        #   stack[k]  = the k-th reaction card, cancels k-1 (kind='reaction'), k>=1
        # Every frame is a REAL cancellation of the one below it (a mere decline never
        # creates a frame — it only advances the flat remaining_candidates within a layer),
        # so resolution is a clean alternation from the top: the top card always takes effect
        # (nothing above it to cancel it), and each card below takes effect iff the card
        # directly above it did NOT. Equivalently, frame k resolves iff its distance from the
        # top (n - k) is even, where n = len(stack) - 1 = number of reaction cards.
        #   depth 1 (n=0): original resolves.                         (nobody cancelled)
        #   depth 2 (n=1): original cancelled, reaction[1] resolves.  (single cancel)
        #   depth 3 (n=2): original resolves, [2] resolves, [1] dead. (counter-cancel)
        #   depth 4 (n=3): original cancelled, [3]&[1] resolve, [2] dead. (counter-counter)
        stack = list(resolution_stack or [])
        if not stack:
            return {'success': True}
        n = len(stack) - 1
        # Resolve the reaction cards top-down so each bonus draw / cancel effect fires in the
        # order they were played (outermost first). frame[1] (the direct canceller of the
        # original) is handled by _resume_reaction_pending_action below when the original is
        # cancelled, so skip it here in that case to avoid double-resolving it.
        original_resolves = (n % 2 == 0)
        for k in range(n, 0, -1):
            if not original_resolves and k == 1:
                continue
            ctx = stack[k].get('reaction_context')
            if ctx is None:
                continue
            if (n - k) % 2 == 0:
                self._apply_reaction_cancel_flags(ctx)
                self._resolve_reaction_context(ctx)
            else:
                self._discard_consumed_reaction_card(ctx)
        orig_choice = stack[0].get('choice') or {}
        if original_resolves:
            return self._resume_reaction_pending_action(orig_choice, reaction_context=None)
        # Original was cancelled by frame[1]; let _resume_reaction_pending_action run its
        # canceled path (discard original, no execute) and resolve frame[1]'s own effect,
        # while skip_reaction_resolution keeps it from touching any deeper frame.
        direct_canceller = stack[1].get('reaction_context')
        self._apply_reaction_cancel_flags(direct_canceller)
        return self._resume_reaction_pending_action(
            orig_choice,
            reaction_context=direct_canceller,
            skip_reaction_resolution=False,
        )

    def _build_reaction_context(self, player, played_card, card_name, mode, reaction):
        if mode != 'action' or not reaction:
            return None
        reaction_player_id = reaction.get('player_id')
        reaction_card_index = reaction.get('card_index')
        reaction_player = next((p for p in self.players if getattr(p, 'id', None) == reaction_player_id), None)
        if reaction_player is None or reaction_player == player or reaction_card_index is None:
            return None
        if reaction_card_index < 0 or reaction_card_index >= len(reaction_player.hand):
            return None
        reaction_card = reaction_player.hand[reaction_card_index]
        reaction_card_name = getattr(reaction_card, 'name', str(reaction_card))
        if reaction_card_name not in {'爆料黑幕', '產業滲透', '情報網'}:
            return None

        cost = self._card_purchase_cost(played_card) or {}
        if not self._reaction_card_cancel_predicate(reaction_card_name, cost):
            return None

        reaction_played = reaction_player.hand.pop(reaction_card_index)
        reaction_context = {
            'reacting_player': reaction_player,
            'reaction_card': reaction_played,
            'reaction_card_name': reaction_card_name,
            'canceled_card': played_card,
            'canceled_card_name': card_name,
            'canceled_card_cost': cost,
        }
        # 2026-08-06 使用者回報：playing 爆料黑幕/產業滲透/情報網 *reactively* never counted
        # toward cost-based mission triggers (play_card_with_money/play_card_with_propaganda
        # — e.g. 重大災難「打出購買費用有宣傳的卡牌」), because that tracking only ever lived
        # in play_card()'s own active-play flow, never in this reactive-resolution path. All
        # three reaction cards have both a money and a propaganda cost, so a reactive play is
        # itself a "played card with this cost" event exactly like an active play — tracked
        # here, once, on the act of spending the reaction card (mirrors play_card()'s existing
        # "the act of playing counts even if the card's own effect is later negated/canceled"
        # semantics: a reaction card that itself gets counter-cancelled still counts).
        reaction_played_cost = self._card_purchase_cost(reaction_played) or {}
        if int(reaction_played_cost.get('money', 0) or 0) > 0:
            self._track_event_progress('play_card_with_money', player=reaction_player)
        if int(reaction_played_cost.get('propaganda', 0) or 0) > 0:
            self._track_event_progress('play_card_with_propaganda', player=reaction_player)
        self.turn_log['canceled_card'] = True
        has_propaganda_cost = int(cost.get('propaganda', 0) or 0) > 0
        has_money_cost = int(cost.get('money', 0) or 0) > 0
        if reaction_card_name == '爆料黑幕':
            self.turn_log['canceled_propaganda_card'] = has_propaganda_cost
        elif reaction_card_name == '產業滲透':
            self.turn_log['canceled_money_cost_card'] = has_money_cost
        self.log(f"{reaction_player.name} reacted with {reaction_card_name} to cancel {card_name}")
        return reaction_context

    def _red_army_action_reaction_prompt(self, player, action_name, kwargs):
        virtual_card = Card(action_name, 'command', {})
        reaction_candidates = self._reaction_prompt_candidates(player, virtual_card)
        if not reaction_candidates:
            return None
        first_candidate = reaction_candidates[0]
        return self._set_pending_reaction_choice(
            first_candidate['player'],
            player,
            virtual_card,
            action_name,
            first_candidate['cards'],
            'action',
            {
                'red_army_action_name': action_name,
                'red_army_action_kwargs': dict(kwargs or {}),
            },
            remaining_candidates=reaction_candidates[1:],
        )

    def _resolve_reaction_context(self, reaction_context):
        if reaction_context is None:
            return
        reaction_player = reaction_context['reacting_player']
        reaction_card_name = reaction_context.get('reaction_card_name') or '爆料黑幕'
        if reaction_card_name == '情報網':
            self.effect_engine.execute({'type': 'cancel_card'}, reaction_player, self, context=reaction_context)
        else:
            self.action_engine.execute(reaction_card_name, reaction_player, self, context=reaction_context, include_resources=False)
        return_borrowed = self._return_borrowed_card_to_owner_topdeck(reaction_context['reaction_card'])
        if not return_borrowed and reaction_context['reaction_card'] not in reaction_player.deck.discard_pile:
            reaction_player.deck.discard([reaction_context['reaction_card']])

    def _pending_choice_holds_current_card(self):
        choice = getattr(self, 'pending_choice', None) or {}
        return bool(
            isinstance(choice, dict)
            and choice.get('choice_key') == 'optional_trash'
            and isinstance(choice.get('context'), dict)
            and choice['context'].get('current_card') is not None
        )

    def play_card(self, index, mode=None, target_player_id=None, target_player_ids=None, reaction=None):
        if mode not in {"resource", "action"}:
            return {"error": "Card play mode must be resource or action"}

        player = self.current_player()
        if index < 0 or index >= len(player.hand):
            return {"error": "Invalid index"}
        pending_card = player.hand[index]
        pending_card_name = getattr(pending_card, "name", str(pending_card))
        queueing_map_card = bool(
            self.pending_choice
            and self.pending_choice.get('player_id') == player.id
            and self._choice_is_card_map_interaction(self.pending_choice)
            and self._card_can_queue_map_action(player, pending_card)
            and mode == 'action'
        )
        if self.pending_choice and not queueing_map_card:
            return {"error": "Please resolve the pending choice first"}
        is_red_support_prep_action = (
            self.turn_phase == TurnPhase.EVENT
            and mode == "action"
            and pending_card_name == "紅軍奧援"
            and getattr(player, 'faction_id', None) == 'red_army'
        )
        if self.turn_phase != TurnPhase.ACTION and not is_red_support_prep_action:
            return {"error": "Not in ACTION phase"}
        if mode == "action" and self._card_is_banned_for_player(player, pending_card):
            return {"error": "非暴力：不能打出武裝類卡牌"}
        if mode == "action":
            action_legality = self._card_action_legality(player, pending_card)
            if not action_legality.get('playable', True):
                return {
                    'error': action_legality.get('reason') or '目前無法使用這張卡牌。',
                    **({'no_legal_build_town': True} if action_legality.get('no_legal_build_town') else {}),
                    'card_name': pending_card_name,
                }
        if mode == "action" and pending_card_name in {"爆料黑幕", "產業滲透"}:
            # 這兩張卡的「行動」效果只有 cancel_card + conditional_draw，沒有像情報網
            # 那樣的 choose_one 主動分支；只能在對方打出可取消的牌時，透過反應視窗
            # （_set_pending_reaction_choice／_resolve_reaction_choice）被動觸發，不會
            # 走 play_card()。自己回合主動點「行動」在這裡執行只會取消不存在的目標、
            # 白白浪費這張卡，因此直接擋下，比照其他需要合法對象才能打出的卡片。
            return {"error": f"{pending_card_name}的取消能力只能被動觸發：當其他玩家打出可取消的卡牌時會自動跳出反應視窗。"}
        if mode == "action" and pending_card_name == "合作談判":
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None) if target_player_id is not None else None
            if target is None or target == player:
                return {"error": "合作談判必須指定任意一名其他玩家"}
        if mode == "action" and pending_card_name == "離間":
            other_player_ids = [
                getattr(other, 'id', None)
                for other in self.players
                if other != player
            ]
            selected_ids = target_player_ids
            if selected_ids is None and target_player_id is not None:
                selected_ids = [target_player_id]
            if selected_ids is None:
                if len(other_player_ids) == 1:
                    selected_ids = list(other_player_ids)
                else:
                    return {"error": "離間必須選擇 1 至 3 位其他玩家"}
            if not isinstance(selected_ids, (list, tuple)):
                return {"error": "離間目標格式無效"}
            selected_ids = list(selected_ids)
            if not 1 <= len(selected_ids) <= 3:
                return {"error": "離間必須選擇 1 至 3 位其他玩家"}
            if any(not isinstance(selected_id, str) for selected_id in selected_ids):
                return {"error": "離間目標格式無效"}
            if len(set(selected_ids)) != len(selected_ids):
                return {"error": "離間不能重複選擇同一位玩家"}
            if any(selected_id not in other_player_ids for selected_id in selected_ids):
                return {"error": "離間只能選擇其他有效玩家"}
            target_player_ids = selected_ids
        if mode == "action" and pending_card_name == "走漏風聲" and target_player_id is not None:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None)
            if target is None or target == player:
                return {"error": "走漏風聲必須指定其他玩家"}
        if mode == "action" and pending_card_name in {"武裝者", "武裝小隊", "武裝集團"}:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None) if target_player_id is not None else None
            if target is None or target == player:
                return {"error": "武裝卡必須指定其他玩家"}
            range_context = self._event_card_range_context(player, pending_card)
            if not self._player_has_org_within_steps_of_player(player, target, max_steps=range_context['range_limit'], target_region=range_context['target_region']):
                return {"error": "Target player has no organization within range"}
            if not getattr(target, 'hand', None):
                return {"error": "Target player has no hand cards"}
        if mode == "action" and pending_card_name in {"派遣間諜", "內應間諜"}:
            target = next((p for p in self.players if getattr(p, "id", None) == target_player_id), None) if target_player_id is not None else None
            if target_player_id is not None and (target is None or target == player):
                return {"error": "間諜卡必須指定其他玩家"}
            target_players = [target] if target is not None else self._target_players_for_interaction(player)
            range_context = self._event_card_range_context(player, pending_card)
            if pending_card_name == "派遣間諜":
                valid = bool(self._interactive_support_sacrifice_towns(player, max_steps=range_context['range_limit'], target_players=target_players, target_region=range_context['target_region'], include_shared_source=True))
            else:
                valid = bool(self._interactive_support_dissolve_targets(player, max_steps=range_context['range_limit'], target_players=target_players, target_region=range_context['target_region'], include_shared_source=True))
            if not valid:
                return {"error": "No target organization within range"}

        if (
            queueing_map_card
            and getattr(pending_card, 'card_type', None) == 'support'
            and not self._support_card_has_legal_target(player, pending_card)
        ):
            return {
                "error": "No legal target for interactive support card",
                "no_legal_target": True,
                "card_name": pending_card_name,
            }

        if queueing_map_card:
            self._deferred_build_choice = dict(self.pending_choice or {})
            self.pending_choice = None
        played_card = player.hand.pop(index)
        card_name = pending_card_name

        if mode == "resource":
            if getattr(played_card, 'card_type', None) == 'support':
                if card_name == '紅軍奧援':
                    # 「打出」是行動模式；只有行動模式才依陣營改變卡牌去向。
                    # 資源模式只取得印刷的 1 資金＋1 宣傳，並依一般資源牌規則
                    # 放入使用者自己的棄牌堆。
                    self._gain_red_support_printed_resources(player, played_card)
                    player.deck.discard([played_card])
                    self.log(f"{player.name} 使用紅軍奧援作為資源")
                    return {"success": True}

                player.deck.discard([played_card])
                self.log(f"{player.name} played {card_name} as resource (no resources from support card)")
                return {"success": True}
            for key, value in getattr(played_card, 'resources', {}).items():
                player.resources[key] += value
            self._apply_era_resource_card_bonus(player, played_card)
            purchase_cost = self._card_purchase_cost(played_card)
            if int(purchase_cost.get('money', 0) or 0) > 0:
                self._track_event_progress('play_card_with_money', player=player)
            if int(purchase_cost.get('propaganda', 0) or 0) > 0:
                self._track_event_progress('play_card_with_propaganda', player=player)
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name} as resource")
            return {"success": True}

        effective_type = getattr(played_card, "card_type", None)
        if getattr(played_card, 'name', str(played_card)) == '紅軍奧援' and mode == "action":
            # 2026-08-05 使用者回報：打出紅軍奧援時，對手的爆料黑幕/產業滲透/情報網完全
            # 不會跳出取消詢問——紅軍奧援有自己獨立於一般奧援卡的結算路徑，過去整段在
            # 進到這裡之前就直接執行完畢並 return，從未檢查過反應候選。比照一般奧援卡
            # 在 9e2c6e9 已經做過的「先開反應視窗、再結算效果」延後模式：有候選就延後
            # 呼叫 _commit_red_support_card_play，沒有候選才立即結算（行為與修正前一致）。
            if reaction is None:
                reaction_candidates = self._reaction_prompt_candidates(player, played_card, include_support=True)
                if reaction_candidates:
                    first_candidate = reaction_candidates[0]
                    return self._set_pending_reaction_choice(
                        first_candidate['player'],
                        player,
                        played_card,
                        card_name,
                        first_candidate['cards'],
                        effective_type,
                        {'is_red_support_card': True},
                        support_resolution=None,
                        remaining_candidates=reaction_candidates[1:],
                    )
            return self._commit_red_support_card_play(player, played_card, card_name)
        if self._player_has_ability(player, "國際線") and getattr(played_card, "card_type", None) == "money":
            effective_type = "propaganda"

        # 打出「購買費用有資金/宣傳的牌」類觸發（點燃熱情/樹立信心/商貿組織/基金會·共合會/
        # 民族調和·星星之火/人同此心）要看實際購買費用組成，不能只看卡牌種類分類。
        # 奧援卡同樣有印刷購買費用；依卡面「其它購買費用有…的牌」文字也必須計入。
        purchase_cost = self._card_purchase_cost(played_card) or {}
        cost_has_money = int(purchase_cost.get('money', 0) or 0) > 0
        cost_has_propaganda = int(purchase_cost.get('propaganda', 0) or 0) > 0
        international_line_used = self._player_has_ability(player, "國際線") and cost_has_money
        if international_line_used:
            cost_has_propaganda = True
            cost_has_money = False

        support_resolution = None
        # Snapshot state *before* this card's own cost is counted, so 點燃熱情/樹立信心's
        # "若本回合曾打出其它購買費用有資金/宣傳的牌" ("an *other* card") condition can't be
        # satisfied by a card whose own purchase cost happens to include money/propaganda.
        action_context = {
            'current_card': played_card,
            'card_name': card_name,
            'cost_has_money': cost_has_money,
            'cost_has_propaganda': cost_has_propaganda,
            'prior_played_money_card': self.turn_log.get('played_money_card', False),
            'prior_played_propaganda_card': self.turn_log.get('played_propaganda_card', False),
            'prior_played_nonstarter_names': list(self.turn_log.get('played_nonstarter_names', [])),
            'borrowed_owner_id': getattr(played_card, '_return_to_owner_topdeck', None),
            'borrowed_purchase_area_index': getattr(played_card, '_return_to_purchase_area_index', None),
            'prior_event_progress': dict(self.event_progress) if isinstance(self.event_progress, dict) else self.event_progress,
            'prior_event_notification': dict(self.event_notification) if isinstance(self.event_notification, dict) else self.event_notification,
            'used_faction_ability_names': (
                ['國際線'] if international_line_used else []
            ),
            'hand_index': index,
        }
        # Snapshot used only by the player-initiated-dissolve cancel feature (see
        # `_dissolve_cancel_kwargs`/`cancel_pending_choice`'s rollback_* handling): captures
        # every piece of state this card's play is about to mutate, *before* it mutates it, so
        # a later `cancel_pending_choice()` call -- issued from any stage of a dissolve card's
        # target-selection flow -- can restore the exact pre-play state. Harmless/unread for
        # any card whose flow never opts into `_dissolve_cancel_kwargs()`.
        # contributed_* record exactly what THIS card's own play is about to add to the
        # reference-counted played_money_card/played_propaganda_card/played_nonstarter_names
        # bookkeeping (see Game._new_turn_log / _note_*/_undo_* in this file) -- NOT an absolute
        # prior snapshot. cancel_pending_choice() undoes precisely this card's own contribution
        # (decrementing the shared ref-counts), which -- unlike restoring an absolute snapshot --
        # stays correct no matter what order multiple interleaved cancellable cards' flows are
        # cancelled or confirmed in.
        action_context['_dissolve_cancel_snapshot'] = {
            'card': played_card,
            'hand_index': index,
            'contributed_money_cost': cost_has_money,
            'contributed_propaganda_cost': cost_has_propaganda,
            'contributed_nonstarter_name': (
                card_name if (effective_type == 'support' or card_name not in {"追隨者", "樂捐者"}) else None
            ),
            'borrowed_owner_id': action_context['borrowed_owner_id'],
            'borrowed_purchase_area_index': action_context['borrowed_purchase_area_index'],
            'event_progress': action_context['prior_event_progress'],
            'event_notification': action_context['prior_event_notification'],
        }
        if mode == 'action' and card_name == '情報網':
            range_context = self._event_card_range_context(player, played_card)
            action_context['range_limit'] = range_context['range_limit']
            action_context['target_region'] = range_context['target_region']
        era_followup_target_choice = self._era_followup_target_choice_for_play_card(player, played_card)
        if era_followup_target_choice:
            action_context['era_followup_target_choice'] = era_followup_target_choice
        era_followup_discard_choice = self._era_followup_discard_choice_for_play_card(player, played_card, target_player_id=target_player_id)
        if era_followup_discard_choice:
            action_context['era_followup_discard_choice'] = era_followup_discard_choice
        if target_player_id is not None:
            action_context['target_player_id'] = target_player_id
        if target_player_ids is not None:
            action_context['target_player_ids'] = list(target_player_ids)

        # Once the card is committed to play, record both printed purchase-cost components.
        # Do this before an interactive support flow can return early with pending_choice;
        # conditional cards still use the pre-card snapshot above, so a card cannot satisfy itself.
        if cost_has_money:
            self._note_money_cost_card_played()
        if cost_has_propaganda:
            self._note_propaganda_cost_card_played()

        if effective_type == 'support':
            action_context['hand_index'] = index
            # Reject an illegal interactive support play up front — before committing any
            # board mutation or spending an opponent's reaction card on it. This mirrors
            # the range pre-validation the command-card path does before hand.pop.
            if not self._support_card_has_legal_target(player, played_card):
                player.hand.insert(index, played_card)
                # Synchronous, same call: exactly undoes the _note_* calls just above, no
                # interleaving window exists between them.
                if cost_has_money:
                    self._undo_money_cost_card_played()
                if cost_has_propaganda:
                    self._undo_propaganda_cost_card_played()
                self.log(f"{player.name} could not play {card_name}: no legal target")
                return {
                    "error": "No legal target for interactive support card",
                    "no_legal_target": True,
                    "card_name": card_name,
                }
            # Legal support cards are committed even when their printed effect continues
            # through a pending choice (or gets canceled by a reaction), so cost-based
            # mission progress fires here, on the act of playing — matching the command
            # card path, where a later cancellation does not undo cost-trigger progress.
            if int(purchase_cost.get('money', 0) or 0) > 0:
                self._track_event_progress('play_card_with_money', player=player)
            if int(purchase_cost.get('propaganda', 0) or 0) > 0:
                self._track_event_progress('play_card_with_propaganda', player=player)
            # Captured AFTER this play's own cost-trigger calls above, so
            # _event_progress_delta(event_progress, event_progress_after) sees exactly what
            # THIS play's own _track_event_progress call(s) changed (see _dissolve_cancel_kwargs).
            action_context['_dissolve_cancel_snapshot']['event_progress_after'] = (
                dict(self.event_progress) if isinstance(self.event_progress, dict) else self.event_progress
            )
            # A support card counts toward 展現實力's played-card combo on the act of
            # playing (even if a reaction later cancels it), exactly like a command card,
            # whose name is recorded before its own reaction window below. Recording it
            # here keeps that semantic on the deferred path; the idempotent block after
            # this branch is then a no-op for support cards.
            self._note_nonstarter_name_played(card_name)
            # Open the cancel-reaction window BEFORE the support card mutates the board or
            # opens its own interactive choice, mirroring the deferred command-card path.
            # If a reactor holds an eligible card, defer _execute_support_card into
            # _resume_reaction_pending_action; otherwise resolve it right away.
            if reaction is None:
                reaction_candidates = self._reaction_prompt_candidates(player, played_card, include_support=True)
                if reaction_candidates:
                    first_candidate = reaction_candidates[0]
                    return self._set_pending_reaction_choice(
                        first_candidate['player'],
                        player,
                        played_card,
                        card_name,
                        first_candidate['cards'],
                        effective_type,
                        action_context,
                        support_resolution=None,
                        remaining_candidates=reaction_candidates[1:],
                    )
            support_response = self._commit_support_card_play(player, played_card, card_name, action_context)
            if support_response is not None:
                return support_response
            support_resolution = action_context.get('support_resolution')
        else:
            if int(purchase_cost.get('money', 0) or 0) > 0:
                self._track_event_progress('play_card_with_money', player=player)
            if int(purchase_cost.get('propaganda', 0) or 0) > 0:
                self._track_event_progress('play_card_with_propaganda', player=player)
            # See the matching capture in the support branch above -- same reasoning.
            action_context['_dissolve_cancel_snapshot']['event_progress_after'] = (
                dict(self.event_progress) if isinstance(self.event_progress, dict) else self.event_progress
            )
        # (support cards already recorded their own name above; this covers every other path)
        if effective_type != 'support' and card_name not in {"追隨者", "樂捐者"}:
            self._note_nonstarter_name_played(card_name)

        reaction_context = self._build_reaction_context(player, played_card, card_name, mode, reaction)
        if reaction_context is None and reaction is None:
            reaction_candidates = self._reaction_prompt_candidates(player, played_card)
            if reaction_candidates:
                first_candidate = reaction_candidates[0]
                return self._set_pending_reaction_choice(
                    first_candidate['player'],
                    player,
                    played_card,
                    card_name,
                    first_candidate['cards'],
                    effective_type,
                    action_context,
                    support_resolution=support_resolution,
                    remaining_candidates=reaction_candidates[1:],
                )

        if reaction_context is not None:
            action_context['reaction_context'] = reaction_context
            action_context['card_canceled'] = True
        if effective_type != 'support':
            if card_name in {"派遣間諜", "內應間諜"}:
                if not action_context.get('card_canceled'):
                    spy_result = self._start_card_dissolve_interaction(
                        player,
                        card_name,
                        requires_self_sacrifice=(card_name == "派遣間諜"),
                        range_limit=self._event_card_range_context(player, played_card)['range_limit'],
                        target_player_id=target_player_id,
                        target_region=self._event_card_range_context(player, played_card)['target_region'],
                        extra_context={
                            **({'era_followup_discard_choice': action_context.get('era_followup_discard_choice')} if action_context.get('era_followup_discard_choice') else {}),
                            '_dissolve_cancel_snapshot': action_context.get('_dissolve_cancel_snapshot'),
                            # Deferred, NOT applied immediately (民族調和／星星之火／商貿組織／
                            # 基金會／人同此心 etc.): this dissolve interaction is cancellable
                            # (see the cancellable-dissolve-target-selection feature), so the
                            # play is not truly committed until its flow's FINAL confirmation.
                            # `_settle_deferred_card_play_triggers` (called from
                            # resolve_pending_choice's tail) applies this exactly once the flow
                            # finishes without being cancelled -- mirroring the support-card
                            # interactive-flow path (`_commit_support_card_play`). A cancel
                            # never calls that method, so a cancelled play correctly never fires
                            # it at all -- no drawn card / latched turn_log flag / queued combo
                            # reward can leak past a cancel this way.
                            'post_play_faction_triggers': {
                                'player_id': player.id,
                                'cost_has_money': bool(cost_has_money),
                                'cost_has_propaganda': bool(cost_has_propaganda),
                                'played_card': played_card,
                                'used_faction_ability_names': list(action_context.get('used_faction_ability_names') or []),
                            },
                        },
                    )
                    if spy_result and spy_result.get('pending_choice'):
                        if not action_context.get('removed_current_card'):
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True, **spy_result}
                    return {"error": "No target organization within range"}
            elif card_name in getattr(self.action_engine, 'cards', {}):
                if not action_context.get('card_canceled'):
                    action_result = self.action_engine.execute(card_name, player, self, context=action_context, include_resources=False)
                    if isinstance(action_result, dict) and action_result.get('pending_choice'):
                        self._apply_era_play_card_effects(player, played_card)
                        # Command/organization cards whose effect opens a pending choice
                        # returned before the common tail below. They therefore never
                        # triggered abilities based on the played card's printed purchase
                        # cost. This includes both builds of 組織經驗乙. The play is already
                        # committed at this point, so run the same hook used by immediate
                        # cards exactly once before returning the pending choice.
                        #
                        # NOTE: 情報網's `choose_one` (the one action-engine card in this
                        # feature's scope that can lead to a cancellable nested choice,
                        # `intel_network_dissolve_target`) never reaches this branch -- its
                        # effect_engine.py handler doesn't return a `pending_choice` dict for
                        # `action_engine.execute` to propagate here, so `action_result` is None
                        # and it falls through to the shared tail below instead, which defers
                        # this same hook specifically for 情報網. Every OTHER card reaching this
                        # branch keeps its original immediate-apply timing unchanged.
                        self._apply_card_play_faction_abilities(
                            player,
                            cost_has_money=cost_has_money,
                            cost_has_propaganda=cost_has_propaganda,
                            played_card=played_card,
                            used_faction_ability_names=action_context.get('used_faction_ability_names'),
                        )
                        if not action_context.get('removed_current_card') and not self._pending_choice_holds_current_card():
                            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                                player.deck.discard([played_card])
                        self.log(f"{player.name} played {card_name}")
                        return {"success": True, "pending_choice": True}
            else:
                pass

        self._resolve_reaction_context(reaction_context)

        if self.pending_choice and card_name == '情報網':
            # 情報網's `choose_one` ends up open here despite not going through the
            # action-engine branch's own pending_choice handling above: the underlying
            # effect_engine.py `choose_one` handler calls `_set_pending_option_choice` as a
            # side effect but does not itself return a `pending_choice` dict for
            # `action_engine.execute` to propagate, so it falls through to this shared tail.
            # Defer here too, exactly like every other 情報網/派遣間諜/內應間諜/support-card
            # branch: picking option B leads to the cancellable nested
            # `intel_network_dissolve_target` choice, and firing the trigger now (before the
            # player has even chosen A/B/C) would let a later cancel of that nested choice leave
            # its side effects (drawn cards, latched turn_log flags, queued combo rewards) stuck
            # in place with nothing to undo them. Scoped to 情報網 specifically -- unlike the
            # other branches above, this shared tail is also reached by many ordinary,
            # never-cancellable action-engine cards (e.g. 組織經驗乙), whose existing
            # apply-immediately timing must not change.
            self.pending_choice.setdefault('context', {})['post_play_faction_triggers'] = {
                'player_id': player.id,
                'cost_has_money': bool(cost_has_money),
                'cost_has_propaganda': bool(cost_has_propaganda),
                'played_card': played_card,
                'used_faction_ability_names': list(action_context.get('used_faction_ability_names') or []),
            }
        else:
            self._apply_card_play_faction_abilities(
                player,
                cost_has_money=cost_has_money,
                cost_has_propaganda=cost_has_propaganda,
                played_card=played_card,
                used_faction_ability_names=action_context.get('used_faction_ability_names'),
            )

        build_continuation = self._resume_card_build_queue_if_idle(player)
        if self.pending_choice:
            if not action_context.get('removed_current_card'):
                if not self._return_borrowed_card_to_owner_topdeck(played_card):
                    player.deck.discard([played_card])
            self.log(f"{player.name} played {card_name}")
            response = {"success": True, "pending_choice": True}
            if build_continuation:
                response.update(build_continuation)
            return response

        if not action_context.get('removed_current_card'):
            self._apply_era_play_card_effects(player, played_card)
            if not self._return_borrowed_card_to_owner_topdeck(played_card):
                player.deck.discard([played_card])
        self.log(f"{player.name} played {card_name}")
        return {"success": True}

    def _recover_stale_event_build_choice_if_satisfied(self):
        choice = self.pending_choice or {}
        if choice.get('choice_key') != 'event_build_organization':
            return False
        player = next((p for p in self.players if getattr(p, 'id', None) == choice.get('player_id')), None)
        if player is None:
            return False
        for entry in choice.get('towns') or []:
            town = (entry or {}).get('town')
            if town and player.organizations.get(town, 0) > 0:
                self.pending_choice = None
                self.log(f"{player.name} already had organization in {town}; auto-cleared stale event build choice")
                return True
        return False

    def _resolve_pending_build_choice_for_town(self, player, town):
        choice = self.pending_choice or {}
        if not choice:
            return None
        if choice.get('player_id') != getattr(player, 'id', None):
            return self._pending_board_action_error()
        if choice.get('choice_key') not in {'event_build_organization', 'era_red_build_near_target', 'card_build_organization'}:
            return self._pending_board_action_error()
        towns = choice.get('towns') or []
        for index, entry in enumerate(towns):
            if (entry or {}).get('town') == town:
                return self.resolve_pending_choice(player.id, index)
        return self._pending_board_action_error()

    def _resolve_era_red_discard_to_build_choice(self, player, choice, selected_cards):
        if not selected_cards:
            return {'error': 'Invalid choice count'}
        for card in selected_cards:
            if card not in player.hand:
                return {'error': 'Chosen card not in hand'}
        context = choice.get('context') if isinstance(choice.get('context'), dict) else {}
        effect = context.get('effect') if isinstance(context.get('effect'), dict) else {}
        build_count = len(selected_cards)
        towns = self._era_build_towns_near_target(player, effect)
        if not towns:
            return {'error': 'No valid era build towns'}
        for card in selected_cards:
            player.hand.remove(card)
            player.deck.discard([card])
        discarded_names = [getattr(card, 'name', str(card)) for card in selected_cards]
        source_name = choice.get('source_name') or context.get('era_name') or '時代關卡'
        self._set_pending_town_choice(
            player,
            'era_red_build_near_target',
            towns,
            f"{source_name}：已棄 {build_count} 張手牌，請依序選擇 {build_count} 個城鎮免費建立紅軍組織。",
            source_name=source_name,
            context={
                **context,
                'discarded_cards': discarded_names,
                'remaining_builds': build_count,
                'build_total': build_count,
                'built_towns': [],
            },
        )
        self.log(f"{player.name} discarded {build_count} card(s) for {source_name}")
        return {
            'success': True,
            'discarded_cards': discarded_names,
            'discarded_count': build_count,
            'choice_key': choice.get('choice_key'),
            'pending_choice': True,
            'town_count': len(towns),
            'remaining_builds': build_count,
        }

    def _era_followup_target_choice_for_play_card(self, player, card):
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'bonus_dissolve_on_red_card_near_self':
                continue
            if not self._player_matches_camp(player, effect.get('player_faction')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            targets = self._era_bonus_dissolve_targets_for_effect(player, effect)
            if not targets:
                continue
            era_name = era.get('name', era.get('id', '時代關卡'))
            return {
                'era_id': era.get('id'),
                'era_name': era_name,
                'targets': targets,
                'max_steps': int((effect or {}).get('max_steps', 1) or 1),
                'target_camp': (effect or {}).get('target_camp'),
                'card_name': getattr(card, 'name', str(card)),
            }
        return None

    def _era_followup_discard_choice_for_play_card(self, player, card, target_player_id=None):
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'bonus_discard_on_red_card':
                continue
            if not self._player_matches_camp(player, effect.get('player_faction')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            targets = self._target_players_for_interaction(player, target_player_id)
            target_camp = effect.get('target_camp')
            target = next(
                (
                    other for other in targets
                    if other is not None
                    and self._player_matches_camp(other, target_camp)
                    and getattr(other, 'hand', None)
                ),
                None,
            )
            if target is None:
                continue
            return {
                'era_id': era.get('id'),
                'era_name': era.get('name', era.get('id', '時代關卡')),
                'target_player_id': getattr(target, 'id', None),
                'target_player_name': getattr(target, 'name', str(getattr(target, 'id', ''))),
                'initiator_player_id': getattr(player, 'id', None),
                'initiator_player_name': getattr(player, 'name', str(getattr(player, 'id', ''))),
                'card_name': getattr(card, 'name', str(card)),
                'discard_count': int(effect.get('discard_count', 1) or 1),
            }
        return None

    def _start_era_followup_discard_choice(self, payload):
        if not isinstance(payload, dict):
            return None
        target = next((p for p in self.players if getattr(p, 'id', None) == payload.get('target_player_id')), None)
        if target is None or not getattr(target, 'hand', None):
            return None
        count = min(int(payload.get('discard_count', 1) or 1), len(target.hand))
        if count <= 0:
            return None
        era_name = payload.get('era_name') or '時代關卡'
        prompt = f"{era_name}：紅軍打出 {payload.get('card_name') or '間諜類卡牌'}，請棄掉 {count} 張手牌。"
        extra = {
            'source_name': era_name,
            'initiator_player_id': payload.get('initiator_player_id'),
            'initiator_player_name': payload.get('initiator_player_name') or '紅軍',
            'target_player_name': payload.get('target_player_name') or getattr(target, 'name', '目標玩家'),
            'context': {
                'era_id': payload.get('era_id'),
                'era_name': era_name,
                'card_name': payload.get('card_name'),
            },
        }
        if count == 1:
            result = self._set_pending_card_choice(target, 'era_bonus_discard_on_red_card', list(target.hand), prompt, **extra)
        else:
            result = self._set_pending_multi_card_choice(target, 'era_bonus_discard_on_red_card', list(target.hand), prompt, count=count, **extra)
        self.turn_log.setdefault('era_effects_applied', []).append({
            'era': payload.get('era_id'),
            'type': 'bonus_discard_on_red_card',
            'status': 'pending_discard_choice',
            'target_player_id': getattr(target, 'id', None),
            'discard_count': count,
        })
        self.log(f"Era {era_name}: {target.name} must discard {count} after Red Army played {payload.get('card_name')}")
        return result

    def _start_era_followup_target_choice(self, payload):
        if not isinstance(payload, dict):
            return None
        red = self._red_player()
        if red is None:
            return None
        era_name = payload.get('era_name') or '時代關卡'
        targets = list(payload.get('targets') or [])
        if not targets:
            return None
        result = self._set_pending_target_choice(
            red,
            'era_red_bonus_dissolve_target',
            targets,
            f"{era_name}：紅軍選擇 1 個維吾爾組織瓦解。",
            source_name=era_name,
            context={
                'era_id': payload.get('era_id'),
                'era_name': era_name,
                'max_steps': payload.get('max_steps', 1),
                'target_camp': payload.get('target_camp'),
                'card_name': payload.get('card_name'),
            },
        )
        self.turn_log.setdefault('era_effects_applied', []).append({
            'era': payload.get('era_id'),
            'type': 'bonus_dissolve_on_red_card_near_self',
            'status': 'pending_target_choice',
            'target_count': len(targets),
        })
        self.log(f"Era {era_name}: {red.name} may dissolve 1 target organization after playing {payload.get('card_name')}")
        return result

    def _apply_era_play_card_effects(self, player, card):
        applied = []
        for era, _side, effect in self._active_era_effects():
            if (effect or {}).get('type') != 'gain_resource_on_play_card':
                continue
            if not self._player_matches_camp(player, effect.get('target_camp')):
                continue
            if not self._card_matches_types(card, effect.get('card_types') or []):
                continue
            resource = effect.get('resource')
            amount = int(effect.get('amount', 0) or 0)
            if resource not in {'money', 'propaganda'} or amount <= 0:
                continue
            player.resources[resource] += amount
            applied.append({'era': era.get('id'), 'type': effect.get('type'), 'resource': resource, 'amount': amount})
            self.log(f"Era {era.get('name', era.get('id'))}: {player.name} gained {amount} {resource} for playing {getattr(card, 'name', str(card))}")
        if applied:
            self.turn_log.setdefault('era_effects_applied', []).extend(applied)
        return applied

