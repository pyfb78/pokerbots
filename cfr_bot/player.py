from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import random
import pickle
import holdem_calc

RANK_TO_VALUE = {
    '2': 2,  '3': 3,  '4': 4,  '5': 5,  '6': 6,
    '7': 7,  '8': 8,  '9': 9,  'T': 10, 'J': 11,
    'Q': 12, 'K': 13, 'A': 14
}

SAVE_FILE = "cfr_data.pkl"

DEBUG_MODE = True  # Toggle debug logging

def debug_log(message):
    if DEBUG_MODE:
        print(message)

class CFRBot(Bot):
    def __init__(self):
        self.opponent_tendencies = {
            'aggression': 0,
            'passivity': 0,
            'bluffing': 0
        }
        self.regret_sum = {}
        self.strategy_sum = {}
        self.strategy_iteration = 0  # Track iterations for strategy adjustments
        self.load_cfr_data()

    def load_cfr_data(self):
        try:
            with open(SAVE_FILE, "rb") as f:
                data = pickle.load(f)
                self.regret_sum = data.get("regret_sum", {})
                self.strategy_sum = data.get("strategy_sum", {})
                debug_log("CFR data loaded successfully.")
        except FileNotFoundError:
            debug_log("No previous CFR data found. Starting fresh.")

    def save_cfr_data(self):
        data = {
            "regret_sum": self.regret_sum,
            "strategy_sum": self.strategy_sum
        }
        with open(SAVE_FILE, "wb") as f:
            pickle.dump(data, f)
        debug_log("CFR data saved successfully.")

    def track_opponent_behavior(self, round_state, active):
        opp_contribution = STARTING_STACK - round_state.stacks[1 - active]
        if opp_contribution > BIG_BLIND * 2:
            self.opponent_tendencies['aggression'] += 1
        elif opp_contribution == 0:
            self.opponent_tendencies['passivity'] += 1
        debug_log(f"Opponent tendencies updated: {self.opponent_tendencies}")

    def calculate_equity(self, board_cards, my_cards):
        """Calculate hand equity using the holdem_calc module."""
        if board_cards:
            equity = holdem_calc.calculate(
                list(board_cards), False, 10000, None, [my_cards[0], my_cards[1], "?", "?"], False
            )
            debug_log(f"Equity calculated: {equity:.4f}")
            return equity
        debug_log("No board cards, equity set to 0.5 (default pre-flop).")
        return 0.5

    def get_strategy(self, state_key, legal_actions):
        regrets = self.regret_sum.get(state_key, {a: 0 for a in legal_actions})
        normalizing_sum = sum(max(r, 0) for r in regrets.values())
        strategy = {a: max(regrets[a], 0) / normalizing_sum if normalizing_sum > 0 else 1 / len(legal_actions) for a in legal_actions}

        if state_key not in self.strategy_sum:
            self.strategy_sum[state_key] = {a: 0 for a in legal_actions}
        for action in legal_actions:
            self.strategy_sum[state_key][action] += strategy[action]

        debug_log(f"Strategy for state {state_key}: {strategy}")
        return strategy

    def update_regret_sum(self, state_key, action, regret):
        if state_key not in self.regret_sum:
            self.regret_sum[state_key] = {}
        if action not in self.regret_sum[state_key]:
            self.regret_sum[state_key][action] = 0
        self.regret_sum[state_key][action] += regret
        debug_log(f"Regret updated for {action}: {regret}. Total: {self.regret_sum[state_key][action]}")

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()
        street = round_state.street
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        pot_size = STARTING_STACK - round_state.stacks[active] + STARTING_STACK - round_state.stacks[1 - active]

        debug_log(f"Round State: Street={street}, My Cards={my_cards}, Board Cards={board_cards}")

        self.track_opponent_behavior(round_state, active)

        equity = self.calculate_equity(board_cards, my_cards)

        state_key = (street, tuple(sorted(my_cards)), tuple(board_cards))
        strategy = self.get_strategy(state_key, legal_actions)

        for action in legal_actions:
            if action == CallAction:
                regret = equity - (pot_size / (pot_size + BIG_BLIND))  # Pot odds comparison
            elif action == RaiseAction:
                regret = equity - 0.6  # Encourage raising if equity is high (threshold = 0.6)
            else:
                regret = -equity  # Discourage folding with high equity

            self.update_regret_sum(state_key, action, regret)

        legal_strategy = {action: strategy[action] for action in legal_actions if action in strategy}
        total_weight = sum(legal_strategy.values())
        if total_weight > 0:
            legal_strategy = {action: weight / total_weight for action, weight in legal_strategy.items()}
        else:
            legal_strategy = {action: 1 / len(legal_actions) for action in legal_actions}

        debug_log(f"Legal strategy: {legal_strategy}")

        chosen_action = random.choices(list(legal_strategy.keys()), weights=legal_strategy.values(), k=1)[0]
        debug_log(f"Chosen action: {chosen_action}")

        if isinstance(chosen_action, RaiseAction):
            min_raise, max_raise = round_state.raise_bounds()
            raise_amount = min_raise + (max_raise - min_raise) // 2
            debug_log(f"Raise amount: {raise_amount}")
            return RaiseAction(raise_amount)
        if isinstance(chosen_action, CallAction):
            return CallAction()
        if isinstance(chosen_action, CheckAction):
            return CheckAction()
        if isinstance(chosen_action, FoldAction):
            return FoldAction()

        debug_log("Defaulting to CheckAction.")
        return CheckAction()

    def handle_new_round(self, game_state, round_state, active):
        debug_log("New round started.")

    def handle_round_over(self, game_state: GameState, terminal_state: TerminalState, active: int):
        self.save_cfr_data()
        debug_log("Round over. Data saved.")

    def save_on_game_end(self):
        self.save_cfr_data()
        debug_log("Game ended. Final data saved.")

if __name__ == '__main__':
    bot = CFRBot()
    try:
        run_bot(bot, parse_args())
    finally:
        bot.save_on_game_end()
        debug_log("Bot execution finished.")

