import random
from enum import Enum
from collections import Counter
from typing import List, Tuple

# Make sure you have these imports from your competition framework
from bot import Bot
from type.poker_action import PokerAction
from type.round_state import RoundStateClient

# --- Helper Enums and Classes ---

class HandRank(Enum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8

class HandCategory(Enum):
    MONSTER = 5         # Full House or better, strong sets
    STRONG_MADE = 4     # Top Pair Top Kicker, Two Pair, Sets
    MEDIUM_MADE = 3     # Decent Top Pair, Middle Pair
    WEAK_MADE = 2       # Bottom Pair, Weak Pair
    STRONG_DRAW = 1     # Combo draws, Flush draws, Open-ended straight draws
    WEAK_DRAW = 0.5     # Gutshot straight draws
    AIR = 0             # No made hand, no significant draw

class Card:
    """Represents a single playing card."""
    def __init__(self, card_str: str):
        if not card_str:
            self.rank = 0
            self.suit = ''
            return
        rank_str = card_str[:-1]
        self.suit = card_str[-1]

        rank_map = {'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        try:
            self.rank = int(rank_map.get(rank_str, rank_str))
        except ValueError:
            self.rank = 0 # Handle potential empty strings or malformed card data gracefully

    def __repr__(self):
        if self.rank == 0: return ""
        rank_map_rev = {10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        return f"{rank_map_rev.get(self.rank, str(self.rank))}{self.suit}"

class HandEvaluator:
    """Evaluates a 5-7 card hand to find its best 5-card combination."""

    def evaluate(self, hand: List[Card], community: List[Card]) -> Tuple[HandRank, List[int]]:
        all_cards = sorted(hand + community, key=lambda c: c.rank, reverse=True)
        if len(all_cards) < 5:
            # Not enough cards for a full hand, can still evaluate pairs/draws
            return self._evaluate_preliminary(all_cards)

        from itertools import combinations
        best_rank = HandRank.HIGH_CARD
        best_kickers = [c.rank for c in all_cards][:5]

        for combo in combinations(all_cards, 5):
            combo = list(combo)
            rank, kickers = self._evaluate_five_card_hand(combo)
            if rank.value > best_rank.value:
                best_rank = rank
                best_kickers = kickers
            elif rank.value == best_rank.value:
                for i in range(len(kickers)):
                    if kickers[i] > best_kickers[i]:
                        best_kickers = kickers
                        break
                    if kickers[i] < best_kickers[i]:
                        break
        return best_rank, best_kickers

    def _evaluate_preliminary(self, cards: List[Card]):
        ranks = [c.rank for c in cards]
        rank_counts = Counter(ranks)

        if 4 in rank_counts.values(): return HandRank.FOUR_OF_A_KIND, sorted(ranks, reverse=True)
        if 3 in rank_counts.values(): return HandRank.THREE_OF_A_KIND, sorted(ranks, reverse=True)
        if list(rank_counts.values()).count(2) >= 1: return HandRank.PAIR, sorted(ranks, reverse=True)

        return HandRank.HIGH_CARD, sorted(ranks, reverse=True)

    def _evaluate_five_card_hand(self, hand: List[Card]) -> Tuple[HandRank, List[int]]:
        ranks = sorted([c.rank for c in hand], reverse=True)
        suits = [c.suit for c in hand]
        rank_counts = Counter(ranks)

        is_flush = len(set(suits)) == 1

        is_straight = False
        unique_ranks = sorted(list(set(ranks)))
        # Ace-low straight check
        if set(ranks) == {14, 2, 3, 4, 5}:
            is_straight = True
            ranks = [5, 4, 3, 2, 1] # Re-order for tie-breaking
        elif len(unique_ranks) >= 5:
            for i in range(len(unique_ranks) - 4):
                if unique_ranks[i] - unique_ranks[i+4] == -4:
                    is_straight = True
                    break

        if is_straight and is_flush: return HandRank.STRAIGHT_FLUSH, ranks

        counts = sorted(rank_counts.values(), reverse=True)
        main_ranks = sorted(rank_counts.keys(), key=lambda r: (rank_counts[r], r), reverse=True)

        if counts[0] == 4: return HandRank.FOUR_OF_A_KIND, main_ranks
        if counts == [3, 2]: return HandRank.FULL_HOUSE, main_ranks
        if is_flush: return HandRank.FLUSH, ranks
        if is_straight: return HandRank.STRAIGHT, ranks
        if counts[0] == 3: return HandRank.THREE_OF_A_KIND, main_ranks
        if counts == [2, 2, 1]: return HandRank.TWO_PAIR, main_ranks
        if counts[0] == 2: return HandRank.PAIR, main_ranks

        return HandRank.HIGH_CARD, ranks

# --- The Main Bot Class ---

class GTOPlayer(Bot):
    def __init__(self):
        super().__init__()
        self.hand: List[Card] = []
        self.evaluator = HandEvaluator()
        self.is_preflop_aggressor = False
        self.all_player_ids = []

        # Simplified GTO-inspired Pre-flop Ranges
        self.preflop_ranges = {
            'EARLY': {
                'RFI': ['77+', 'ATs+', 'KJs+', 'QJs', 'JTs', 'T9s', 'AJo+', 'KQo'],
                'vs_raise': {'3bet': ['TT+', 'AQs+', 'AKo'], 'call': ['22-99', 'AJs', 'ATs', 'KQs']}
            },
            'MIDDLE': {
                'RFI': ['55+', 'A8s+', 'K9s+', 'QTs+', 'JTs', 'T9s', 'A9o+', 'KTo+', 'QJo'],
                'vs_raise': {'3bet': ['99+', 'ATs+', 'KJs+', 'AQo+'], 'call': ['22-88', 'A9s', 'KTs', 'QTs']}
            },
            'LATE': {
                'RFI': ['22+', 'A2s+', 'K7s+', 'Q8s+', 'J8s+', 'T8s+', 'A2o+', 'K9o+', 'QTo+', 'JTo'],
                'vs_raise': {'3bet': ['88+', 'A8s+', 'K9s+', 'AQo+', 'KQo'], 'call': ['22-77', 'A2s-A7s', 'JTs', 'QTs']}
            },
            'BLINDS': {
                'RFI': ['33+', 'A2s+', 'K8s+', 'Q9s+', 'J9s+', 'A7o+', 'KTo+'],
                'vs_raise': {'3bet': ['99+', 'AJs+', 'AQo+'], 'call': ['22-88', 'A2s-ATs', 'KJs+', 'QTs+']}
            }
        }

    def on_start(self, starting_chips: int, player_hands: List[str], blind_amount: int, big_blind_player_id: int, small_blind_player_id: int, all_players: List[int]):
        self.all_player_ids = all_players
        my_hand_str = player_hands[0]
        self.hand = [Card(c) for c in my_hand_str.split(" ")]
        print(f"Player {self.id} started game with hand {self.hand}")

    def on_round_start(self, round_state: RoundStateClient, remaining_chips: int):
        self.is_preflop_aggressor = False
        print(f"--- Round {round_state.round} ---")

    def get_action(self, round_state: RoundStateClient, remaining_chips: int) -> Tuple[PokerAction, int]:
        amount_to_call = round_state.current_bet - round_state.player_bets.get(str(self.id), 0)

        if round_state.round == 'Preflop':
            return self._get_preflop_action(round_state, amount_to_call)

        community_cards = self.community_cards(round_state)
        hand_rank, _ = self.evaluator.evaluate(self.hand, community_cards)
        hand_category = self._categorize_hand(hand_rank, self.hand, community_cards)
        pot_size = round_state.pot

        if amount_to_call == 0: # We can check or bet
            if self.is_preflop_aggressor:
                if hand_category.value >= HandCategory.STRONG_MADE.value or hand_category.value == HandCategory.STRONG_DRAW.value:
                    return self._make_bet(round_state, int(pot_size * 0.66))
                elif hand_category.value == HandCategory.AIR.value and random.random() < 0.4:
                    return self._make_bet(round_state, int(pot_size * 0.4))
                else:
                    return PokerAction.CHECK, 0
            else:
                if hand_category.value >= HandCategory.MEDIUM_MADE.value:
                    return self._make_bet(round_state, int(pot_size * 0.5))
                else:
                    return PokerAction.CHECK, 0
        else: # Facing a bet
            pot_odds = amount_to_call / (pot_size + amount_to_call) if (pot_size + amount_to_call) > 0 else 0

            if hand_category.value == HandCategory.MONSTER.value:
                return self._make_raise(round_state, int(pot_size * 1.5 + amount_to_call))
            if hand_category.value >= HandCategory.STRONG_MADE.value:
                return PokerAction.CALL, amount_to_call
            if hand_category.value == HandCategory.STRONG_DRAW.value:
                equity = self._estimate_draw_equity(community_cards)
                if equity > pot_odds:
                    return PokerAction.CALL, amount_to_call
            if hand_category.value >= HandCategory.WEAK_MADE.value:
                if amount_to_call <= pot_size * 0.5:
                    return PokerAction.CALL, amount_to_call

            return PokerAction.FOLD, 0

    def on_end_round(self, round_state: RoundStateClient, remaining_chips: int):
        pass

    def on_end_game(self, round_state: RoundStateClient, player_score: float, all_scores: dict, active_players_hands: dict):
        pass

    def _get_preflop_action(self, round_state: RoundStateClient, amount_to_call: int):
        position = self._get_position(round_state)
        ranges = self.preflop_ranges[position]

        has_raise = any(action == "Raise" for action in round_state.player_actions.values())

        if has_raise:
            if self._is_in_range(ranges['vs_raise']['3bet']):
                self.is_preflop_aggressor = True
                return self._make_raise(round_state, round_state.current_bet * 3)
            elif self._is_in_range(ranges['vs_raise']['call']):
                return PokerAction.CALL, amount_to_call
            else:
                return PokerAction.FOLD, 0
        else:
            if self._is_in_range(ranges['RFI']):
                self.is_preflop_aggressor = True
                return self._make_raise(round_state, round_state.min_raise * 2.5)
            elif amount_to_call == 0:
                return PokerAction.CHECK, 0
            else:
                return PokerAction.FOLD, 0

    def _get_position(self, round_state: RoundStateClient) -> str:
        player_count = len(self.all_player_ids)
        if player_count <= 3: return 'LATE'
        try:
            my_index = self.all_player_ids.index(self.id)
            bb_index = self.all_player_ids.index(round_state.big_blind_player_id)
            relative_pos = (my_index - bb_index + player_count) % player_count
        except ValueError:
            return 'LATE' # Fallback

        if relative_pos in [player_count - 1, player_count - 2]: return 'BLINDS'
        if relative_pos == player_count - 3: return 'LATE' # Button
        if relative_pos == player_count - 4: return 'LATE' # Cutoff
        if relative_pos == player_count - 5: return 'MIDDLE'
        return 'EARLY'

    def _is_in_range(self, range_list: List[str]) -> bool:
        hand_str = self._get_hand_string()
        c1, c2 = self.hand
        for r in range_list:
            if len(r) == 2: # Pair like '77'
                if hand_str.startswith(r): return True
            elif r.endswith('+'):
                base_rank_str = r[1]
                base_rank = Card(base_rank_str + 's').rank
                if len(r) == 3 and r[0] == r[1]: # Pair range like '99+'
                    if c1.rank == c2.rank and c1.rank >= base_rank: return True
                elif r.endswith('s+') and hand_str.endswith('s'): # Suited range like 'ATs+'
                    if hand_str[0] == r[0] and c2.rank >= base_rank: return True
                elif r.endswith('o+') and hand_str.endswith('o'): # Offsuit range like 'AJo+'
                    if hand_str[0] == r[0] and c2.rank >= base_rank: return True
            elif r == hand_str:
                return True
        return False

    def _get_hand_string(self) -> str:
        c1, c2 = sorted(self.hand, key=lambda c: c.rank, reverse=True)
        s = 's' if c1.suit == c2.suit else 'o'
        rank_map_rev = {10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        r1 = rank_map_rev.get(c1.rank, str(c1.rank))
        r2 = rank_map_rev.get(c2.rank, str(c2.rank))
        return f"{r1}{r2}" if r1 == r2 else f"{r1}{r2}{s}"

    def community_cards(self, round_state: RoundStateClient) -> List[Card]:
        return [Card(c) for c in round_state.community_cards]

    def _categorize_hand(self, rank: HandRank, hand: List[Card], community: List[Card]) -> HandCategory:
        if rank.value >= HandRank.FULL_HOUSE.value: return HandCategory.MONSTER
        if rank == HandRank.THREE_OF_A_KIND and hand[0].rank == hand[1].rank: return HandCategory.MONSTER
        if rank.value >= HandRank.TWO_PAIR.value: return HandCategory.STRONG_MADE

        combined = hand + community
        if len(combined) < 5:
            suits = [c.suit for c in combined]
            if Counter(suits).most_common(1)[0][1] == 4: return HandCategory.STRONG_DRAW
            unique_ranks = sorted(list(set(c.rank for c in combined)))
            if len(unique_ranks) >= 4:
                for i in range(len(unique_ranks)-3):
                    if unique_ranks[i+3] - unique_ranks[i] <= 4: return HandCategory.STRONG_DRAW

        if rank == HandRank.PAIR:
            pair_rank = [r for r, c in Counter([c.rank for c in combined]).items() if c==2][0]
            if pair_rank in [hand[0].rank, hand[1].rank] and pair_rank >= max([c.rank for c in community], default=0):
                return HandCategory.STRONG_MADE
            if pair_rank in [hand[0].rank, hand[1].rank]: return HandCategory.MEDIUM_MADE
            return HandCategory.WEAK_MADE

        return HandCategory.AIR

    def _estimate_draw_equity(self, community_cards: List[Card]) -> float:
        outs = 0
        combined = self.hand + community_cards
        if Counter([c.suit for c in combined]).most_common(1)[0][1] == 4: outs += 9

        unique_ranks = sorted(list(set(c.rank for c in combined)))
        if len(unique_ranks) >= 4:
            is_oesd = any(unique_ranks[i+3] - unique_ranks[i] == 3 for i in range(len(unique_ranks)-3))
            if is_oesd: outs = max(outs, 8)
            else:
                is_gutshot = any(unique_ranks[i+3] - unique_ranks[i] == 4 for i in range(len(unique_ranks)-3))
                if is_gutshot: outs = max(outs, 4)

        multiplier = 4 if len(community_cards) == 3 else 2
        return (outs * multiplier) / 100

    def _make_bet(self, round_state: RoundStateClient, amount: int) -> Tuple[PokerAction, int]:
        amount = int(amount)
        min_bet = round_state.min_raise
        max_bet = round_state.max_raise
        clamped_amount = max(min_bet, min(amount, max_bet))
        return PokerAction.RAISE, clamped_amount

    def _make_raise(self, round_state: RoundStateClient, amount: int) -> Tuple[PokerAction, int]:
        amount = int(amount)
        min_raise = round_state.min_raise
        max_raise = round_state.max_raise
        clamped_amount = max(min_raise, min(amount, max_raise))
        return PokerAction.RAISE, clamped_amount