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
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your action.
        '''
        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        street = round_state.street  # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active]  # your cards
        board_cards = round_state.deck[:street]  # the board cards
        my_pip = round_state.pips[active]  # the number of chips you have contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]  # the number of chips your opponent has contributed to the pot this round of betting
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        my_bounty = round_state.bounties[active]  # your current bounty rank
        my_contribution = STARTING_STACK - my_stack  # the number of chips you have contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack  # the number of chips your opponent has contributed to the pot

        min_raise = 0
        max_raise = 0

        # Raise bounds, if raising is allowed
        if RaiseAction in legal_actions:
            min_raise, max_raise = round_state.raise_bounds()
            min_cost = min_raise - my_pip
            max_cost = max_raise - my_pip
        else:
            min_raise, max_raise = None, None

        # 1. Identify if we hold the bounty rank in our hole cards
        #    or if the board has our bounty rank
        has_bounty_in_hand = any(card.rank == my_bounty for card in my_cards)
        bounty_on_board = any(card.rank == my_bounty for card in board_cards)

        # 2. Evaluate hole cards (extremely naive approach):
        #    - Are they a high pair (TT, JJ, QQ, KK, AA)?
        #    - Do we at least have an Ace or King?
        ranks = [RANK_TO_VALUE[c.rank] for c in my_cards]
        ranks.sort()
        is_pair = (my_cards[0].rank == my_cards[1].rank)
        high_pair = is_pair and ranks[0] >= 10  # TT or better

        has_ace = any(c.rank == 'A' for c in my_cards)
        has_king = any(c.rank == 'K' for c in my_cards)

        # 3. Combine logic with the bounty card:
        #    If we have a high pair or a bounty card,
        #    or if the bounty card has appeared on the board,
        #    we’ll be more aggressive.

        # We’ll define a naive "aggression score" based on these features:
        aggression_score = 0

        # Increase aggression if we have a high pair
        if high_pair:
            aggression_score += 2

        # Some moderate boost if we hold an ace or king
        if has_ace or has_king:
            aggression_score += 1

        # Big boost if the hole cards contain the bounty rank
        if has_bounty_in_hand:
            aggression_score += 2

        # If the bounty rank appears on the board, small additional boost
        if bounty_on_board:
            aggression_score += 1

        # 4. Decide your action based on aggression score
        #    (this is a simplistic demonstration)
        # Higher scores => more likely to raise
        # Lower scores => call or fold

        # Try raising if it's allowed
        if RaiseAction in legal_actions:
            # For simplicity, pick a size that’s either a min_raise or a mid-range raise
            # based on how “aggressive” we are.
            if aggression_score >= 3:
                # be more aggressive
                raise_amount = min_raise + int(0.5 * (max_raise - min_raise))
                return RaiseAction(raise_amount)
            elif aggression_score == 2:
                return RaiseAction(min_raise)

        # If we can’t raise or we decided not to raise, see if we can check
        if CheckAction in legal_actions and continue_cost == 0:
            return CheckAction()

        # If we must call or fold
        # Fold if we’re not feeling it (low aggression + random factor)
        if aggression_score < 1 and random.random() < 0.4:
            # 40% of the time fold if we’re not strong
            return FoldAction()

        # Otherwise, default to call
        return CallAction()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
