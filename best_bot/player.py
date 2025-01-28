import pandas as pd
import random
import holdem_calc
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
import os
import eval7

SAVE_FILE = "cfr_data.csv"
DEBUG_MODE = True

RANK_TO_VALUE = {
    '2': 2,  '3': 3,  '4': 4,  '5': 5,  '6': 6,
    '7': 7,  '8': 8,  '9': 9,  'T': 10, 'J': 11,
    'Q': 12, 'K': 13, 'A': 14
}
def get_action_from_string(chosen_action):
    # Extract class name from the string
    if chosen_action.startswith("<class '") and chosen_action.endswith("'>"):
        class_path = chosen_action[len("<class '"):-len("'>")]  # Remove <class ''> wrapper
        class_name = class_path.split('.')[-1]  # Extract class name (e.g., 'CallAction')
        # Map class names to actual classes
        action_map = {
            "FoldAction": FoldAction,
            "CallAction": CallAction,
            "CheckAction": CheckAction,
            "RaiseAction": RaiseAction
        }
        # Return the corresponding class if it exists
        return action_map.get(class_name, None)
    return None  # Return None if string is not a valid class representation

def is_valid_action_instance(chosen_action_str, obj):

    action_class = get_action_from_string(chosen_action_str)  # Get the action class from the string

    if action_class:

        return isinstance(obj, action_class)  # Check if the object is an instance of the action class

    return False

def debug_log(message):
    if DEBUG_MODE:
        print(message)

class Player(Bot):
    def __init__(self):
        self.opponent_tendencies = {
            'aggression_frequency': 0.0,
            'bluff_count': 0,
            'total_actions': 0,
            'raise_count': 0
        }
        self.regret_sum = {}
        self.strategy_sum = {}
        self.strategy_iteration = 0
        self.bounty = None
        self.load_cfr_data()

    def load_cfr_data(self):
        try:
            if not os.path.exists(SAVE_FILE) or os.path.getsize(SAVE_FILE) == 0:
                debug_log("No previous CFR data found. Starting fresh.")
                return

            df = pd.read_csv(SAVE_FILE)
            for _, row in df.iterrows():
                state_key = tuple(row['state_key'].split('|'))
                action = row['action']
                regret = row['regret']
                strategy = row['strategy']
                if state_key not in self.regret_sum:
                    self.regret_sum[state_key] = {}
                if state_key not in self.strategy_sum:
                    self.strategy_sum[state_key] = {}
                self.regret_sum[state_key][action] = regret
                self.strategy_sum[state_key][action] = strategy
            debug_log("CFR data loaded successfully.")
        except FileNotFoundError:
            debug_log("No previous CFR data found. Starting fresh.")
        except pd.errors.EmptyDataError:
            debug_log("CFR data file is empty. Starting fresh.")

    def save_cfr_data(self):
        rows = []
        for state_key, actions in self.regret_sum.items():
            for action, regret in actions.items():
                strategy = self.strategy_sum[state_key].get(action, 0)
                rows.append({
                    'state_key': '|'.join(map(str, state_key)),  # Convert all elements to strings
                    'action': action,
                    'regret': regret,
                    'strategy': strategy
                })
        df = pd.DataFrame(rows)
        df.to_csv(SAVE_FILE, index=False)
        debug_log("CFR data saved successfully.")

    def get_strategy(self, state_key, legal_actions):
        # Ensure that all legal_actions have an entry in regrets, even if not present
        regrets = self.regret_sum.get(state_key, {action: 0 for action in legal_actions})
        for action in legal_actions:
            if action not in regrets:
                regrets[action] = 0  # Initialize missing actions

        # Ensure that all actions have an entry in strategy_sum
        if state_key not in self.strategy_sum:
            self.strategy_sum[state_key] = {}
        for action in legal_actions:
            if action not in self.strategy_sum[state_key]:
                self.strategy_sum[state_key][action] = 0  # Initialize missing actions
        if RaiseAction in regrets:
            regrets[RaiseAction] += 0.2  # Increase raise tendency

        normalizing_sum = sum(max(r, 0) for r in regrets.values())
        strategy = {a: max(regrets[a], 0) / normalizing_sum if normalizing_sum > 0 else 1 / len(legal_actions) for a in legal_actions}

        # Update the strategy_sum with the calculated strategy
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

    def track_opponent_behavior(self, round_state, active):
        opp_pip = round_state.pips[1 - active]
        opp_stack = round_state.stacks[1 - active]
        opp_contribution = STARTING_STACK - opp_stack

        self.opponent_tendencies['total_actions'] += 1

        if opp_contribution > BIG_BLIND * 2:
            self.opponent_tendencies['raise_count'] += 1

        self.opponent_tendencies['aggression_frequency'] = (
            self.opponent_tendencies['raise_count'] / self.opponent_tendencies['total_actions']
        )

        if opp_pip > 0 and random.random() < 0.2:
            self.opponent_tendencies['bluff_count'] += 1

        debug_log(f"Opponent tendencies updated: {self.opponent_tendencies}")

    # def calculate_equity(self, board_cards, my_cards):
    #     if len(board_cards) > 0:
    #         debug_log(board_cards)
    #         _, equity, _ = holdem_calc.calculate(
    #             list(board_cards), False, 5000, None, [my_cards[0], my_cards[1], "?", "?"], False
    #         )
    #         debug_log(f"Equity calculated: {equity:.4f}")
           
    #         return equity

    #     high_card_rank = max(RANK_TO_VALUE[my_cards[0][0]], RANK_TO_VALUE[my_cards[1][0]])
    #     return 0.7 if high_card_rank >= 11 else 0.5
    
    def calculate_equity(self, board_cards, my_cards, iterations=1000):
        """
        Calculate the equity of a known hand (hand1) against a random opponent hand,
        with optional known community cards (board). Accepts card strings as input.

        Args:
            hand1 (list): A list of 2 card strings (e.g., ["As", "Ks"]) representing the known hand.
            known_board (list): A list of card strings (e.g., ["2h", "7d", "5s"]) representing known community cards.
                                Pass an empty list or None if there are no known cards.
            iterations (int): Number of Monte Carlo iterations.

        Returns:
            float: Equity percentage for hand1.
        """
        # Convert string inputs to eval7.Card objects
        hand1 = [eval7.Card(card) for card in my_cards]
        if board_cards:
            known_board = [eval7.Card(card) for card in board_cards]
        else:
            known_board = []

        wins = 0  # Number of wins for hand1
        ties = 0  # Number of ties
        total = 0  # Total simulations

        # Create a deck and remove known cards (hand1 and known_board)
        deck = eval7.Deck()
        for card in hand1:
            deck.cards.remove(card)  # Remove hand1 cards from the deck
        for card in known_board:
            deck.cards.remove(card)  # Remove known board cards from the deck

        for _ in range(iterations):
            deck.shuffle()  # Shuffle the deck

            # Randomly select a two-card opponent hand
            opp_hand = deck.peek(2)

            # Determine the number of remaining community cards to deal
            remaining_board_count = 5 - len(known_board)

            # Deal the remaining community cards
            remaining_board = deck.peek(remaining_board_count)  # Peek after opponent's hand

            # Combine the known and remaining community cards
            board = known_board + remaining_board

            # Evaluate both hands
            score1 = eval7.evaluate(hand1 + board)
            score2 = eval7.evaluate(opp_hand + board)

            if score1 > score2:
                wins += 1
            elif score1 == score2:
                ties += 1

            total += 1

        equity = (wins + ties / 2) / total
        return equity

    def dynamic_raise_amount(self, equity, pot_size, min_raise, max_raise):
        aggression_frequency = self.opponent_tendencies['aggression_frequency']
        bluff_count = self.opponent_tendencies['bluff_count']

        base_aggression = equity * 5

        if aggression_frequency > 0.6:
            base_aggression *= 0.8

        if bluff_count > 20:
            base_aggression *= 2

        raise_amount = pot_size * min(3.5, base_aggression)
        raise_amount = max(min_raise, min(raise_amount, max_raise))
        debug_log(f"Dynamic raise amount calculated with tendencies: {raise_amount}")
        return raise_amount

    def get_action(self, game_state, round_state, active):
        # return FoldAction()
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
                regret = equity - (pot_size / (pot_size + BIG_BLIND))
            elif action == RaiseAction:
                regret = equity - 0.6
            else:
                regret = -equity
            self.update_regret_sum(state_key, action, regret)

        legal_strategy = {action: strategy[action] for action in legal_actions if action in strategy}
        debug_log(f"Legal strategy: {legal_strategy}")

        if not legal_strategy or sum(legal_strategy.values()) == 0:
            debug_log("No valid strategy available. Defaulting to FoldAction.")
            return FoldAction()
        # return FoldAction()
        chosen_action = random.choices(list(legal_strategy.keys()), weights=legal_strategy.values(), k=1)[0]
        # debug_log(f"Chosen action: {chosen_action}")
        debug_log(f'checking type {str(chosen_action)}')
   
        r = RaiseAction(5)
        check = CheckAction()
        call = CallAction()
        fold = FoldAction()
        # return CheckAction() 
        if(is_valid_action_instance(str(chosen_action), r)):
            min_raise, max_raise = round_state.raise_bounds()
            raise_amount = self.dynamic_raise_amount(equity, pot_size, min_raise, max_raise)
            debug_log(f"sent answer: {RaiseAction(raise_amount)}")
            return RaiseAction(int(raise_amount))
        # return FoldAction() 
        if(is_valid_action_instance(str(chosen_action), check)):
            debug_log(f"sent answer: {CheckAction()}")
            return CheckAction()
        # return CheckAction()
        if(is_valid_action_instance(str(chosen_action), fold)):
            debug_log(f"sent answer: {FoldAction()}")
            return FoldAction()

        debug_log("Defaulting to CallAction.")
        return CallAction()

    def handle_new_round(self, game_state, round_state, active):
        debug_log("New round started.")
        self.bounty = round_state.bounties[active]
        debug_log(f"Bounty for this round: {self.bounty}")

    def handle_round_over(self, game_state: GameState, terminal_state: TerminalState, active: int):
        # self.save_cfr_data()
        debug_log("Round over. Data saved.")

    def save_on_game_end(self):
        # self.save_cfr_data()
        debug_log("Game ended. Final data saved.")

if __name__ == '__main__':
    run_bot(Player(), parse_args())

