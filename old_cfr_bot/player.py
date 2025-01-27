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
            'aggression_frequency': 0.0,  # Ratio of raises to total actions
            'bluff_count': 0,             # Number of suspected bluffs
            'total_actions': 0,           # Total actions observed
            'raise_count': 0              # Total raises observed
        }
        self.regret_sum = {}
        self.strategy_sum = {}
        self.strategy_iteration = 0  # Track iterations for strategy adjustments
        self.bounty = None  # Initialize bounty rank
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
        opp_pip = round_state.pips[1 - active]
        opp_stack = round_state.stacks[1 - active]
        opp_contribution = STARTING_STACK - opp_stack

        # Increment total actions
        self.opponent_tendencies['total_actions'] += 1

        # Identify aggression
        if opp_contribution > BIG_BLIND * 2:
            self.opponent_tendencies['raise_count'] += 1

        # Calculate aggression frequency
        self.opponent_tendencies['aggression_frequency'] = (
            self.opponent_tendencies['raise_count'] / self.opponent_tendencies['total_actions']
        )

        # Detect potential bluffing (simplistic heuristic: raising with low equity)
        if opp_pip > 0 and random.random() < 0.2:
            self.opponent_tendencies['bluff_count'] += 1

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

    def calculate_bounty_multiplier(self, my_cards, board_cards):
        """Check if the bounty rank is in the hole cards or on the board."""
        combined = my_cards + board_cards
        bounty_hit = any(card[0] == self.bounty for card in combined)
        return 1.5 if bounty_hit else 1.0

    def dynamic_raise_amount(self, equity, pot_size, min_raise, max_raise):
        """Calculate a dynamic raise amount based on equity and pot size."""
        aggression_factor = min(1.5, equity * 2)  # Scale raise aggression based on equity
        raise_amount = pot_size * aggression_factor
        raise_amount = max(min_raise, min(raise_amount, max_raise))
        debug_log(f"Dynamic raise amount calculated: {raise_amount}")
        return raise_amount

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

    def adjust_strategy_based_on_tendencies(self, strategy):
        """Adjust strategy dynamically based on opponent tendencies."""
        aggression_frequency = self.opponent_tendencies['aggression_frequency']
        bluff_count = self.opponent_tendencies['bluff_count']

        # Adjust strategy against aggressive opponents
        if aggression_frequency > 0.6:
            strategy[CallAction] = strategy.get(CallAction, 0) + 0.2
            strategy[RaiseAction] = strategy.get(RaiseAction, 0) - 0.2
        
        # Adjust strategy against bluff-heavy opponents
        if bluff_count > 5:
            strategy[CallAction] = strategy.get(CallAction, 0) + 0.3

        # Normalize strategy
        total_weight = sum(strategy.values())
        if total_weight > 0:
            strategy = {action: weight / total_weight for action, weight in strategy.items()}

        debug_log(f"Adjusted strategy based on tendencies: {strategy}")
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
        bounty_multiplier = self.calculate_bounty_multiplier(my_cards, board_cards)
        effective_equity = equity * bounty_multiplier

        debug_log(f"Effective equity (considering bounty): {effective_equity:.4f}")

        state_key = (street, tuple(sorted(my_cards)), tuple(board_cards))
        strategy = self.get_strategy(state_key, legal_actions)

        for action in legal_actions:
            if action == CallAction:
                regret = effective_equity - (pot_size / (pot_size + BIG_BLIND))
            elif action == RaiseAction:
                regret = effective_equity - 0.6
            else:
                regret = -effective_equity

            self.update_regret_sum(state_key, action, regret)

        legal_strategy = {action: strategy[action] for action in legal_actions if action in strategy}
        legal_strategy = self.adjust_strategy_based_on_tendencies(legal_strategy)

        chosen_action = random.choices(list(legal_strategy.keys()), weights=legal_strategy.values(), k=1)[0]
        debug_log(f"Chosen action: {chosen_action}")

        if chosen_action not in legal_actions:
            debug_log(f"Chosen action {chosen_action} not legal, defaulting to FoldAction.")
            return FoldAction()

        if isinstance(chosen_action, RaiseAction):
            min_raise, max_raise = round_state.raise_bounds()
            raise_amount = self.dynamic_raise_amount(effective_equity, pot_size, min_raise, max_raise)
            return RaiseAction(raise_amount)
        if isinstance(chosen_action, CallAction):
            return CallAction()
        if isinstance(chosen_action, CheckAction):
            return CheckAction()
        if isinstance(chosen_action, FoldAction):
            return FoldAction()

        debug_log("Defaulting to FoldAction.")
        return FoldAction()

    def handle_new_round(self, game_state, round_state, active):
        debug_log("New round started.")
        self.bounty = round_state.bounties[active]
        debug_log(f"Bounty for this round: {self.bounty}")

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

