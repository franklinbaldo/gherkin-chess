from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import chess

from .models import FeatureModel, ScenarioModel
from .corpus import CorpusManager


def board_features(board: chess.Board) -> Dict[str, Any]:
    """
    Extract structural and tactical traits from a chess.Board for context matching.
    """
    is_check = board.is_check()
    turn = "white" if board.turn == chess.WHITE else "black"
    move_number = board.fullmove_number
    
    phase = "opening"
    if move_number > 30 or len(board.piece_map()) <= 12:
        phase = "endgame"
    elif move_number > 10:
        phase = "middlegame"

    # Material balance count
    counts = {
        "P": 0, "N": 0, "B": 0, "R": 0, "Q": 0, "K": 0,
        "p": 0, "n": 0, "b": 0, "r": 0, "q": 0, "k": 0
    }
    for piece in board.piece_map().values():
        counts[piece.symbol()] += 1

    # Checks/threats
    attacked_valuable = []
    for sq, piece in board.piece_map().items():
        if piece.color == board.turn and piece.piece_type in (chess.QUEEN, chess.ROOK, chess.KNIGHT, chess.BISHOP):
            if board.is_attacked_by(not board.turn, sq):
                attacked_valuable.append(chess.square_name(sq))

    return {
        "turn": turn,
        "is_check": is_check,
        "phase": phase,
        "move_number": move_number,
        "attacked_pieces": attacked_valuable,
        "piece_count": len(board.piece_map()),
    }


def fen_piece_placement(fen: str) -> str:
    """Return piece placement part of FEN string."""
    return fen.split(" ")[0]


def position_similarity(fen1: str, fen2: str) -> float:
    """
    Compute similarity between two positions based on board structure.
    Score between 0.0 and 1.0.
    """
    try:
        b1 = chess.Board(fen1)
        b2 = chess.Board(fen2)
    except Exception:
        return 0.0

    # Piece overlap on identical squares
    m1 = b1.piece_map()
    m2 = b2.piece_map()
    common_squares = set(m1.keys()) & set(m2.keys())
    matching_pieces = sum(1 for sq in common_squares if m1[sq].symbol() == m2[sq].symbol())

    total_pieces = max(len(m1), len(m2), 1)
    overlap_score = matching_pieces / total_pieces

    # Phase similarity
    f1 = board_features(b1)
    f2 = board_features(b2)
    phase_bonus = 0.2 if f1["phase"] == f2["phase"] else 0.0
    check_bonus = 0.1 if f1["is_check"] == f2["is_check"] else 0.0

    return min(1.0, overlap_score * 0.7 + phase_bonus + check_bonus)


class ScenarioMatch:
    def __init__(self, scenario: ScenarioModel, feature: FeatureModel, score: float, reasons: List[str]):
        self.scenario = scenario
        self.feature = feature
        self.score = score
        self.reasons = reasons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario.name,
            "feature_name": self.feature.name,
            "origin_fen": self.feature.origin_fen,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "gherkin": self.scenario.to_gherkin(),
        }


def retrieve_relevant_scenarios(
    board: chess.Board,
    corpus: CorpusManager,
    limit: int = 5,
) -> List[ScenarioMatch]:
    """
    Retrieve top relevant scenarios from the OKF corpus for the given board.
    Considers:
    1. Similarity between current board FEN and Scenario's origin_fen.
    2. Context tags and step keywords matching current board features (check, phase, attacks).
    """
    features = corpus.load_all_features()
    if not features:
        return []

    curr_fen = board.fen()
    curr_traits = board_features(board)
    matches: List[ScenarioMatch] = []

    for feat in features:
        fen_sim = 0.0
        reasons = []
        if feat.origin_fen:
            fen_sim = position_similarity(curr_fen, feat.origin_fen)
            if fen_sim > 0.4:
                reasons.append(f"Position similarity with origin_fen: {fen_sim:.2f}")

        # Trait keywords
        trait_terms = set()
        if curr_traits["is_check"]:
            trait_terms.update(["xeque", "check", "mate", "ameaça", "threat", "rei", "king"])
        if curr_traits["phase"] == "opening":
            trait_terms.update(["abertura", "opening", "desenvolvimento", "development", "centro", "center"])
        elif curr_traits["phase"] == "endgame":
            trait_terms.update(["final", "endgame", "peão", "pawn", "promoção", "promotion"])
        if curr_traits["attacked_pieces"]:
            trait_terms.update(["ataque", "attack", "cravada", "pin", "garfo", "fork", "captura", "capture"])

        for sc in feat.scenarios:
            sc_score = fen_sim * 0.6
            sc_reasons = list(reasons)

            # Check text in tags and steps
            sc_text = (sc.name + " " + sc.description + " " + " ".join(s.text for s in sc.steps)).lower()
            sc_tags = [t.lower() for t in sc.tags + feat.tags]

            tag_hits = [t for t in trait_terms if any(t in tag for tag in sc_tags)]
            if tag_hits:
                sc_score += 0.25
                sc_reasons.append(f"Tag matches: {', '.join(tag_hits)}")

            text_hits = [t for t in trait_terms if t in sc_text]
            if text_hits:
                sc_score += 0.25
                sc_reasons.append(f"Content matches: {', '.join(text_hits)}")

            if sc_score > 0.05:
                matches.append(ScenarioMatch(scenario=sc, feature=feat, score=sc_score, reasons=sc_reasons))

    # Sort descending by score
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]