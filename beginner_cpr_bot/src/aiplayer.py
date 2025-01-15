import random
# import pyttsx3
import numpy as np
from player import Player
# from abstraction import calculate_equity
from preflop_holdem import PreflopHoldemHistory, PreflopHoldemInfoSet
from postflop_holdem import PostflopHoldemHistory, PostflopHoldemInfoSet
import joblib
import copy


def getAction(strategy):
    return np.random.choice(list(strategy.keys()), p=list(strategy.values()))


class AIPlayer(Player):
    def __init__(self, balance) -> None:
        super().__init__(balance)
        self.is_AI = True
        self.speak = True

    def process_action(self, action, observed_env):
        if action == "k":  # check
            if observed_env.game_stage == 2:
                self.current_bet = observed_env.BIG_BLIND
            else:
                self.current_bet = 0

        elif action == "c":
            # If you call on the preflop
            self.current_bet = observed_env.get_highest_current_bet()
        elif action == "f":
            print("fold")
        else:
            self.current_bet = int(action[1:])

class CFRAIPlayer(AIPlayer):
    def __init__(self, balance) -> None:
        super().__init__(balance)

        self.preflop_infosets = joblib.load("../src/preflop_infoSets_batch_19.joblib")
        self.postflop_infosets = joblib.load("../src/postflop_infoSets_batch_19.joblib")

    def place_bet(self, observed_env):
        card_str = [str(card) for card in self.hand]
        community_cards = [str(card) for card in observed_env.community_cards]

        isDealer = self == observed_env.get_player(observed_env.dealer_button_position)
        checkAllowed = "k" in observed_env.valid_actions()

        action = self.get_action(
            observed_env.history,
            card_str,
            community_cards,
            observed_env.get_highest_current_bet(),
            observed_env.stage_pot_balance,
            observed_env.total_pot_balance,
            self.player_balance,
            observed_env.BIG_BLIND,
            isDealer,
            checkAllowed,
        )
        self.process_action(action, observed_env)  # use voice activation
        return action

    def get_action(
        self,
        history,
        card_str,
        community_cards,
        highest_current_bet,
        stage_pot_balance,
        total_pot_balance,
        player_balance,
        BIG_BLIND,
        isDealer,
        checkAllowed,
    ):

        # Bet sizing uses the pot balance
        # stage_pot_balance used for preflop, total_pot_balance used for postflop

        action = None
        HEURISTICS = False  # Use in case my preflop strategy sucks

        SMALLEST_BET = int(BIG_BLIND / 2)
        if len(community_cards) == 0:  # preflop
            if HEURISTICS:
                player = EquityAIPlayer(self.player_balance)
                action = player.get_action(
                    card_str,
                    community_cards,
                    total_pot_balance,
                    highest_current_bet,
                    BIG_BLIND,
                    player_balance,
                    isDealer,
                    checkAllowed,
                )
            else:
                abstracted_history = self.perform_preflop_abstraction(history, BIG_BLIND=BIG_BLIND)
                infoset_key = "".join(PreflopHoldemHistory(abstracted_history).get_infoSet_key())
                strategy = self.preflop_infosets[infoset_key].get_average_strategy()
                abstracted_action = getAction(strategy)
                if abstracted_action == "bMIN":
                    action = "b" + str(max(BIG_BLIND, int(stage_pot_balance)))
                elif abstracted_action == "bMID":
                    action = "b" + str(max(BIG_BLIND, 2 * int(stage_pot_balance)))
                elif abstracted_action == "bMAX":  # all-in... oh god
                    action = "b" + str(player_balance)
                else:
                    action = abstracted_action

                print("history: ", history)
                print("Abstracted history: ", abstracted_history)
                print("Infoset key: ", infoset_key)
                print("AI strategy ", strategy)
                print("Abstracted Action:", abstracted_action, "Final Action:", action)
        else:
            abstracted_history = self.perform_postflop_abstraction(
                history, BIG_BLIND=BIG_BLIND
            )  # condense down bet sequencing
            infoset_key = PostflopHoldemHistory(abstracted_history).get_infoSet_key_online()
            strategy = self.postflop_infosets[infoset_key].get_average_strategy()
            abstracted_action = getAction(strategy)
            print("Abstracted action: ", action)
            if abstracted_action == "bMIN":
                action = "b" + str(
                    max(BIG_BLIND, int(1 / 3 * total_pot_balance / SMALLEST_BET) * SMALLEST_BET)
                )
            elif abstracted_action == "bMAX":
                action = "b" + str(min(total_pot_balance, player_balance))
            else:
                action = abstracted_action

            print("history: ", history)
            print("Abstracted history: ", abstracted_history)
            print("Infoset key: ", infoset_key)
            print("AI strategy ", strategy)
            print("Abstracted Action:", abstracted_action, "Final Action:", action)

        return action

    def perform_preflop_abstraction(self, history, BIG_BLIND=2):
        stage = copy.deepcopy(history)
        abstracted_history = stage[:2]
        if (
            len(stage) >= 6 and stage[3] != "c"  # bet seqeuence of length 4
        ):  # length 6 that isn't a call, we need to condense down
            if len(stage) % 2 == 0:
                abstracted_history += ["bMAX"]
            else:
                abstracted_history += ["bMIN", "bMAX"]
        else:
            bet_size = BIG_BLIND
            pot_total = BIG_BLIND + int(BIG_BLIND / 2)
            for i, action in enumerate(stage[2:]):
                if action[0] == "b":
                    bet_size = int(action[1:])

                    # this is a raise on a small bet
                    if abstracted_history[-1] == "bMIN":
                        if bet_size <= 2 * pot_total:
                            abstracted_history += ["bMID"]
                        else:
                            abstracted_history += ["bMAX"]
                    elif abstracted_history[-1] == "bMID":
                        abstracted_history += ["bMAX"]
                    elif abstracted_history[-1] == "bMAX":
                        if abstracted_history[-2] == "bMID":
                            abstracted_history[-2] = "bMIN"
                        abstracted_history[-1] = "bMID"
                        abstracted_history += ["bMAX"]
                    else:  # first bet
                        if bet_size <= pot_total:
                            abstracted_history += ["bMIN"]
                        elif bet_size <= 2 * pot_total:
                            abstracted_history += ["bMID"]
                        else:
                            abstracted_history += ["bMAX"]

                    pot_total += bet_size

                elif action == "c":
                    pot_total = 2 * bet_size
                    abstracted_history += ["c"]
                else:
                    abstracted_history += [action]
        return abstracted_history

    def perform_postflop_abstraction(self, history, BIG_BLIND=2):
        history = copy.deepcopy(history)

        pot_total = BIG_BLIND * 2
        # Compute preflop pot size
        flop_start = history.index("/")
        for i, action in enumerate(history[:flop_start]):
            if action[0] == "b":
                bet_size = int(action[1:])
                pot_total = 2 * bet_size

        # ------- Remove preflop actions + bet abstraction -------
        abstracted_history = history[:2]
        # swap dealer and small blind positions for abstraction
        stage_start = flop_start
        stage = self.get_stage(history[stage_start + 1 :])
        latest_bet = 0
        while True:
            abstracted_history += ["/"]
            if (
                len(stage) >= 4 and stage[3] != "c"
            ):  # length 4 that isn't a call, we need to condense down
                abstracted_history += [stage[0]]

                if stage[-1] == "c":
                    if len(stage) % 2 == 1:  # ended on dealer
                        abstracted_history += ["bMAX", "c"]
                    else:
                        if stage[0] == "k":
                            abstracted_history += ["k", "bMAX", "c"]
                        else:
                            abstracted_history += ["bMIN", "bMAX", "c"]
                else:
                    if len(stage) % 2 == 0:
                        abstracted_history += ["bMAX"]
                    else:
                        abstracted_history += ["bMIN", "bMAX"]
            else:
                for i, action in enumerate(stage):
                    if action[0] == "b":
                        bet_size = int(action[1:])
                        latest_bet = bet_size

                        # this is a raise on a small bet
                        if abstracted_history[-1] == "bMIN":
                            abstracted_history += ["bMAX"]
                        # this is a raise on a big bet
                        elif (
                            abstracted_history[-1] == "bMAX"
                        ):  # opponent raised, first bet must be bMIN
                            abstracted_history[-1] = "bMIN"
                            abstracted_history += ["bMAX"]
                        else:  # first bet
                            if bet_size >= pot_total:
                                abstracted_history += ["bMAX"]
                            else:
                                abstracted_history += ["bMIN"]

                        pot_total += bet_size

                    elif action == "c":
                        pot_total += latest_bet
                        abstracted_history += ["c"]
                    else:
                        abstracted_history += [action]

            # Proceed to next stage or exit if final stage
            if "/" not in history[stage_start + 1 :]:
                break
            stage_start = history[stage_start + 1 :].index("/") + (stage_start + 1)
            stage = self.get_stage(history[stage_start + 1 :])

        return abstracted_history

    def get_stage(self, history):
        if "/" in history:
            return history[: history.index("/")]
        else:
            return history
