from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
import holdem_calc

class EquityBot(Bot):
    """
    A poker bot that uses equity calculations to make decisions in a 2-player game.
    """

    def __init__(self):
        """
        Initialize the bot.
        """
        pass

    def handle_new_round(self, game_state: GameState, round_state: RoundState, active: int):
        """
        Called at the start of each round.
        """
        pass

    def handle_round_over(self, game_state: GameState, terminal_state: TerminalState, active: int):
        """
        Called at the end of each round.
        """
        pass

    def get_action(self, game_state: GameState, round_state: RoundState, active: int):
        """
        Determine the bot's action based on equity calculations.

        Arguments:
        - game_state: The GameState object.
        - round_state: The RoundState object.
        - active: The index of the bot.

        Returns:
        - An action (FoldAction, CallAction, CheckAction, RaiseAction).
        """
        legal_actions = round_state.legal_actions()  # Legal actions for the bot.
        street = round_state.street  # 0 = pre-flop, 3 = flop, 4 = turn, 5 = river.
        my_cards = round_state.hands[active]  # Bot's hole cards.
        board_cards = round_state.deck[:street]  # Community cards.
        my_pip = round_state.pips[active]  # Chips bot has contributed this round.
        opp_pip = round_state.pips[1 - active]  # Chips opponent has contributed this round.
        my_stack = round_state.stacks[active]  # Bot's remaining chips.
        opp_stack = round_state.stacks[1 - active]  # Opponent's remaining chips.
        continue_cost = opp_pip - my_pip  # Chips needed to call.

        # Pre-flop logic: Play tighter without community cards.
        if street == 0:
            equity = holdem_calc.calculate([], False, 100, None, [my_cards[0], my_cards[1], "?", "?"], False)
            win_equity = equity[1]

            if win_equity > 0.6:  # Strong hand.
                if RaiseAction in legal_actions:
                    min_raise, _ = round_state.raise_bounds()
                    return RaiseAction(min_raise)
                return CallAction()  # If raising isn't possible, call.
            elif win_equity > 0.4:  # Decent hand.
                return CallAction() if CallAction in legal_actions else CheckAction()
            else:  # Weak hand.
                return FoldAction() if FoldAction in legal_actions else CheckAction()

        # Post-flop logic: Use community cards to adjust strategy.
        equity = holdem_calc.calculate(
            list(board_cards), False, 10000, None, [my_cards[0], my_cards[1], "?", "?"], False
        )
        win_equity = equity[1]

        if win_equity > 0.7:  # Very strong hand.
            if RaiseAction in legal_actions:
                min_raise, _ = round_state.raise_bounds()
                return RaiseAction(min_raise)
            return CallAction()  # Aggressive play.
        elif win_equity > 0.5:  # Moderate strength.
            return CallAction() if CallAction in legal_actions else CheckAction()
        elif win_equity > 0.3:  # Weak but playable.
            return CheckAction() if CheckAction in legal_actions else FoldAction()
        else:  # Very weak hand.
            return FoldAction() if FoldAction in legal_actions else CheckAction()

if __name__ == "__main__":
    run_bot(EquityBot(), parse_args())

