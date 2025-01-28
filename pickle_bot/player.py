import random
import pickle
import os
from functools import lru_cache
import eval7
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

SAVE_FILE = "cfr_data.pkl"
DEBUG_MODE = True

RANK_TO_VALUE = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
    '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11,
    'Q': 12, 'K': 13, 'A': 14
}

class Player(Bot):
    def __init__(self):
        self.opponent_tendencies = {
            'preflop_aggression': 0.0,
            'postflop_bluff': 0.0,
            'street_actions': {0: 0, 3: 0, 4: 0, 5: 0},
            'raise_counts': {0: 0, 3: 0, 4: 0, 5: 0}
        }
        self.regret_sum = {}
        self.strategy_sum = {}
        self.strategy_iteration = 0
        self.bounty = None
        self.load_cfr_data()

    def load_cfr_data(self):
        try:
            with open(SAVE_FILE, 'rb') as f:
                data = pickle.load(f)
                self.regret_sum = data['regret']
                self.strategy_sum = data['strategy']
            debug_log("CFR data loaded successfully.")
        except (FileNotFoundError, EOFError):
            self.regret_sum = {}
            self.strategy_sum = {}
            debug_log("No valid CFR data found. Starting fresh.")

    def save_cfr_data(self):
        data = {
            'regret': self.regret_sum,
            'strategy': self.strategy_sum
        }
        with open(SAVE_FILE, 'wb') as f:
            pickle.dump(data, f)
        debug_log("CFR data saved successfully.")

    def bounty_hit(self, hole_cards, board_cards):
        if not self.bounty:
            return False
        bounty_rank = self.bounty[0] if isinstance(self.bounty, tuple) else self.bounty
        return any(card.startswith(bounty_rank) for card in hole_cards + board_cards)

    def get_average_strategy(self, state_key, legal_actions):
        total = sum(self.strategy_sum.get(state_key, {}).values())
        if total == 0:
            return {action: 1/len(legal_actions) for action in legal_actions}
        return {action: self.strategy_sum[state_key][action]/total for action in legal_actions}

    def get_strategy(self, state_key, legal_actions):
        self.strategy_iteration += 1
        if self.strategy_iteration > 1000:
            legal_actions = [a for a in legal_actions if self.regret_sum.get(state_key, {}).get(a, 0) > -10]

        regrets = {a: self.regret_sum.get(state_key, {}).get(a, 0) for a in legal_actions}
        normalizing_sum = sum(max(r, 0) for r in regrets.values())
        
        if normalizing_sum > 0:
            strategy = {a: max(r, 0)/normalizing_sum for a, r in regrets.items()}
        else:
            strategy = {a: 1/len(legal_actions) for a in legal_actions}

        for action in legal_actions:
            self.strategy_sum.setdefault(state_key, {})[action] = self.strategy_sum.get(state_key, {}).get(action, 0) + strategy[action]
        
        return strategy

    def track_opponent_behavior(self, round_state, active):
        street = round_state.street
        opp_pip = round_state.pips[1 - active]
        
        self.opponent_tendencies['street_actions'][street] += 1
        if opp_pip > BIG_BLIND * 2:
            self.opponent_tendencies['raise_counts'][street] += 1
            
        if street == 0:
            aggression = self.opponent_tendencies['raise_counts'][street] / self.opponent_tendencies['street_actions'][street]
            self.opponent_tendencies['preflop_aggression'] = 0.8 * self.opponent_tendencies['preflop_aggression'] + 0.2 * aggression
        else:
            bluff_prob = (opp_pip - BIG_BLIND) / (STARTING_STACK - round_state.stacks[1 - active] + 1e-6)
            self.opponent_tendencies['postflop_bluff'] = 0.8 * self.opponent_tendencies['postflop_bluff'] + 0.2 * bluff_prob

    @lru_cache(maxsize=5000)
    def cached_equity(self, hole_tuple, board_tuple):
        hole_cards = list(hole_tuple)
        board_cards = list(board_tuple)
        deck = eval7.Deck()
        for card in hole_cards + board_cards:
            deck.cards.remove(eval7.Card(card))
        
        wins, ties = 0, 0
        for _ in range(1000):
            deck.shuffle()
            opp_hole = deck.peek(2)
            remaining_board = 5 - len(board_cards)
            full_board = board_cards + [str(card) for card in deck.peek(remaining_board)]
            
            our_hand = [eval7.Card(c) for c in hole_cards]
            opp_hand = [eval7.Card(str(c)) for c in opp_hole]
            community = [eval7.Card(c) for c in full_board]
            
            our_score = eval7.evaluate(our_hand + community)
            opp_score = eval7.evaluate(opp_hand + community)
            
            if our_score > opp_score:
                wins += 1
            elif our_score == opp_score:
                ties += 1
                
        return (wins + ties/2) / 1000

    def calculate_equity(self, board_cards, my_cards):
        return self.cached_equity(tuple(sorted(my_cards)), tuple(sorted(board_cards)))

    def dynamic_raise_amount(self, equity, pot_size, min_raise, max_raise, hole_cards, board_cards):
        base_aggression = equity * (7 if self.bounty_hit(hole_cards, board_cards) else 5)
        aggression_mod = 1.0
        
        if self.opponent_tendencies['preflop_aggression'] > 0.6:
            aggression_mod *= 0.8
        if self.opponent_tendencies['postflop_bluff'] > 0.4:
            aggression_mod *= 1.2
            
        raise_amount = pot_size * min(3.5, base_aggression * aggression_mod)
        return int(max(min_raise, min(raise_amount, max_raise)))

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()
        street = round_state.street
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        pot_size = sum(round_state.pips)
        bounty_active = self.bounty_hit(my_cards, board_cards)

        state_key = (street, tuple(sorted(my_cards)), tuple(sorted(board_cards)), self.bounty)
        strategy = self.get_strategy(state_key, legal_actions)
        
        equity = self.calculate_equity(board_cards, my_cards)
        bounty_multiplier = 1.5 if bounty_active else 1.0
        fixed_bonus = 10 / (pot_size + 1e-6) if bounty_active else 0

        for action in legal_actions:
            if action == RaiseAction:
                regret = (equity * bounty_multiplier) - 0.6 + fixed_bonus
            elif action == CallAction:
                regret = (equity * bounty_multiplier) - (pot_size / (pot_size + BIG_BLIND)) + fixed_bonus
            else:
                regret = -equity * bounty_multiplier
            self.regret_sum.setdefault(state_key, {})[action] = self.regret_sum.get(state_key, {}).get(action, 0) + regret

        chosen_action = random.choices(list(strategy.keys()), weights=list(strategy.values()))[0]
        
        if chosen_action == RaiseAction:
            min_raise, max_raise = round_state.raise_bounds()
            raise_amt = self.dynamic_raise_amount(equity, pot_size, min_raise, max_raise, my_cards, board_cards)
            return RaiseAction(raise_amt)
        elif chosen_action == CallAction:
            return CallAction()
        elif chosen_action == CheckAction:
            return CheckAction()
        
        return FoldAction()

    def handle_new_round(self, game_state, round_state, active):
        self.bounty = round_state.bounties[active]
        self.strategy_iteration = 0

    def handle_round_over(self, game_state, terminal_state, active):
        if terminal_state.is_split:
            our_bounty = self.bounty_hit(terminal_state.hands[active], terminal_state.deck)
            opp_bounty = self.bounty_hit(terminal_state.hands[1-active], terminal_state.deck)
            
            if our_bounty != opp_bounty:
                delta = (terminal_state.pot_size // 4) + 10
                if our_bounty:
                    game_state.bankrolls[active] += delta
                else:
                    game_state.bankrolls[active] -= delta
        
        self.save_cfr_data()

def debug_log(message):
    if DEBUG_MODE:
        print(message)

if __name__ == '__main__':
    run_bot(Player(), parse_args())
