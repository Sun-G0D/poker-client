from abc import ABC, abstractmethod
from typing import List

from type.round_state import RoundStateClient


class Bot(ABC):
    def __init__(self):
        """ Initializes the player. """
        self.id = None
        pass

    def set_id(self, player_id: int):
        """ Sets the player ID. """
        self.id = player_id

    @abstractmethod
    def on_start(self, starting_chips: int, player_hands: List[str], blind_amount: int, big_blind_player_id: int, small_blind_player_id: int, all_players: List[int]):
        """ Called when the game starts. """
        pass

    @abstractmethod
    def on_round_start(self, round_state: RoundStateClient, remaining_chips: int):
        """ Called at the start of each round. """
        pass

    @abstractmethod
    def get_action(self, round_state: RoundStateClient, remaining_chips: int):
        """ Called when it is the player's turn to act. """
        pass

    @abstractmethod
    def on_end_round(self, round_state: RoundStateClient, remaining_chips: int):
        """ Called at the end of each round. """
        pass

    @abstractmethod
    def on_end_game(self, round_state: RoundStateClient, player_score: float, all_scores: dict, active_players_hands: dict):
        """ Called at the end of the game. """
        pass

class SimplePlayer(Bot):
    def __init__(self):
        super().__init__()

    def on_start(self, starting_chips: int, player_hands: List[str], blind_amount: int, big_blind_player_id: int, small_blind_player_id: int, all_players: List[int]):
        print("Player called on game start")
        print("Player hands: ", player_hands)
        print("Blind: ", blind_amount)
        print("Big blind player id: ", big_blind_player_id)
        print("Small blind player id: ", small_blind_player_id)
        print("All players in game: ", all_players)

    def on_round_start(self, round_state: RoundStateClient, remaining_chips: int):
        print("Player called on round start")
        print("Round state: ", round_state)

    def get_action(self, round_state: RoundStateClient, remaining_chips: int):
        """ Returns the action for the player. """
         ...

    def on_end_round(self, round_state: RoundStateClient, remaining_chips: int):
        """ Called at the end of the round. """
        print("Player called on end round")

    def on_end_game(self, round_state: RoundStateClient, player_score: float, all_scores: dict, active_players_hands: dict):
        print("Player called on end game, with player score: ", player_score)
        print("All final scores: ", all_scores)
        print("Active players hands: ", active_players_hands)