'''
Simple example pokerbot, written in Python.
'''
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

class Player(Bot):
    '''
    A pokerbot.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        pass

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        #my_bankroll = game_state.bankroll  # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        #game_clock = game_state.game_clock  # the total number of seconds your bot has left to play this game
        #round_num = game_state.round_num  # the round number from 1 to NUM_ROUNDS
        #my_cards = round_state.hands[active]  # your cards
        #big_blind = bool(active)  # True if you are the big blind
        #my_bounty = round_state.bounties[active]  # your current bounty rank
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        #my_delta = terminal_state.deltas[active]  # your bankroll change from this round
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        #street = previous_state.street  # 0, 3, 4, or 5 representing when this round ended
        #my_cards = previous_state.hands[active]  # your cards
        #opp_cards = previous_state.hands[1-active]  # opponent's cards or [] if not revealed

        my_bounty_hit = terminal_state.bounty_hits[active]  # True if you hit bounty
        opponent_bounty_hit = terminal_state.bounty_hits[1-active] # True if opponent hit bounty
        bounty_rank = previous_state.bounties[active]  # your bounty rank

        # The following is a demonstration of accessing illegal information (will not work)
        opponent_bounty_rank = previous_state.bounties[1-active]  # attempting to grab opponent's bounty rank

        if my_bounty_hit:
            print("I hit my bounty of " + bounty_rank + "!")
        if opponent_bounty_hit:
            print("Opponent hit their bounty of " + opponent_bounty_rank + "!")

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()
        street = round_state.street
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        my_pip = round_state.pips[active]
        opp_pip = round_state.pips[1-active]
        my_stack = round_state.stacks[active]
        opp_stack = round_state.stacks[1-active]
        pot_size = sum(round_state.pips)
        continue_cost = opp_pip - my_pip
        my_bounty = round_state.bounties[active]

        # Raise bounds
        min_raise, max_raise = None, None
        if RaiseAction in legal_actions:
            min_raise, max_raise = round_state.raise_bounds()

        # Hand Strength Evaluation
        ranks = [RANK_TO_VALUE[c.rank] for c in my_cards]
        ranks.sort()
        is_pair = my_cards[0].rank == my_cards[1].rank
        high_pair = is_pair and ranks[0] >= 10
        has_ace = any(c.rank == 'A' for c in my_cards)
        has_king = any(c.rank == 'K' for c in my_cards)
        suited = my_cards[0].suit == my_cards[1].suit

        # Simple flush or straight draw detection
        potential_flush = len(set(c.suit for c in board_cards + my_cards)) == 1
        potential_straight = len(set(ranks + [RANK_TO_VALUE[c.rank] for c in board_cards])) <= 5

        # Position Awareness
        position = (active == 1)  # True if small blind, False if big blind

        # Pot Odds Calculation
        pot_odds = continue_cost / (pot_size + continue_cost) if continue_cost > 0 else 0

        # Dynamic Aggression Calculation
        aggression_score = 0
        if high_pair:
            aggression_score += 3
        elif has_ace or has_king:
            aggression_score += 2
        if suited or potential_flush:
            aggression_score += 1
        if potential_straight:
            aggression_score += 1

        # Adjust aggression based on position
        if position:
            aggression_score += 1  # Be more aggressive in position

        # Decision Making
        if RaiseAction in legal_actions and aggression_score >= 3:
            raise_amount = min_raise + int(0.5 * (max_raise - min_raise))
            return RaiseAction(raise_amount)
        elif CallAction in legal_actions and pot_odds < 0.5:
            return CallAction()
        elif CheckAction in legal_actions and continue_cost == 0:
            return CheckAction()

        # Fold when aggression and pot odds are low
        if aggression_score < 2 and pot_odds >= 0.5:
            return FoldAction()

        # Default to call
        return CallAction()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
