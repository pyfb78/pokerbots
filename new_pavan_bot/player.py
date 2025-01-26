from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import random

RANK_TO_VALUE = {
    '2': 2,  '3': 3,  '4': 4,  '5': 5,  '6': 6,
    '7': 7,  '8': 8,  '9': 9,  'T': 10, 'J': 11,
    'Q': 12, 'K': 13, 'A': 14
}

def evaluate_hand_strength(my_cards, board_cards):
    """
    Simplistic hand strength evaluation (to be replaced with a proper poker hand evaluator).
    """
    combined = my_cards + board_cards
    ranks = [RANK_TO_VALUE[c.rank] for c in combined]
    ranks.sort(reverse=True)

    # Simple: prioritize pairs, high cards
    is_pair = len(set(ranks)) < len(ranks)
    high_card = max(ranks)

    return (is_pair, high_card)

def calculate_pot_odds(my_pip, opp_pip, pot_size):
    """
    Calculate pot odds to inform call/fold decisions.
    """
    call_cost = opp_pip - my_pip
    if call_cost <= 0:
        return 1.0  # No cost to continue
    return call_cost / (pot_size + call_cost)

def calculate_equity(board_cards, my_cards):
    """
    Calculate hand equity using holdem_calc if board cards are available.
    """
    if board_cards:
        return holdem_calc.calculate(
            list(board_cards), False, 10000, None, [my_cards[0], my_cards[1], "?", "?"], False
        )
    return None

class Player(Bot):
    def __init__(self):
        self.opponent_tendencies = {
            'aggression': 0,
            'passivity': 0,
            'bluffing': 0
        }

    def track_opponent_behavior(self, round_state, active):
        opp_pip = round_state.pips[1 - active]
        opp_contribution = STARTING_STACK - round_state.stacks[1 - active]

        # Simple heuristic: if opponent bets aggressively, track it
        if opp_contribution > BIG_BLIND * 2:
            self.opponent_tendencies['aggression'] += 1
        elif opp_contribution == 0:
            self.opponent_tendencies['passivity'] += 1

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()
        street = round_state.street
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        my_pip = round_state.pips[active]
        opp_pip = round_state.pips[1 - active]
        my_stack = round_state.stacks[active]
        pot_size = STARTING_STACK - my_stack + STARTING_STACK - round_state.stacks[1 - active]

        # Track opponent behavior
        self.track_opponent_behavior(round_state, active)

        # Evaluate hand strength
        is_pair, high_card = evaluate_hand_strength(my_cards, board_cards)

        # Calculate pot odds
        pot_odds = calculate_pot_odds(my_pip, opp_pip, pot_size)

        # Calculate equity if board cards exist
        equity = calculate_equity(board_cards, my_cards)

        # Simple logic: Raise with strong hands, call with pot odds, fold otherwise
        if is_pair or high_card >= 12:  # Pair or strong high card (Q+)
            if RaiseAction in legal_actions:
                min_raise, max_raise = round_state.raise_bounds()
                raise_amount = min_raise + int(0.5 * (max_raise - min_raise))
                return RaiseAction(raise_amount)
        elif pot_odds < 0.5:  # Call if pot odds are favorable
            if CallAction in legal_actions:
                return CallAction()

        if CheckAction in legal_actions:
            return CheckAction()

        return FoldAction()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
