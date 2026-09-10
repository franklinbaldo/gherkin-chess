from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import chess

from .corpus import CorpusManager
from .engine_advisor import EngineAdvisor
from .models import FeatureModel
from .parser import GherkinParseError, parse_gherkin
from .retrieval import retrieve_relevant_scenarios


class IllegalMoveError(ValueError):
    """Raised when a move is not legal in the current board state."""
    pass


class MissingGherkinError(ValueError):
    """Raised when a move is attempted without providing Gherkin."""
    pass


class OriginMismatchError(ValueError):
    """Raised when the Gherkin's origin_fen does not match the pre-move board state."""
    pass


class MoveNotRelatedError(ValueError):
    """Raised when the Gherkin explanation has no connection to the intended move."""
    pass


@dataclass
class MoveRecord:
    move_number: int
    turn: str
    uci: str
    san: str
    pre_fen: str
    post_fen: str
    timestamp: str
    gherkin: str
    recovered_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    engine_advice: Optional[Dict[str, Any]] = None


class ChessGame:
    """
    Manages a single game session, enforcing:
    1. Legality of chess moves.
    2. Mandatory Gherkin justification before move execution.
    3. Gherkin parse validity.
    4. Exact origin_fen match (the FEN right before the move).
    5. Materialization into OKF via okf-parser.
    6. Retrieval of relevant Scenarios from past corpus.
    """

    def __init__(
        self,
        game_id: str,
        corpus: CorpusManager,
        starting_fen: Optional[str] = None,
        advisor: Optional[EngineAdvisor] = None,
    ):
        self.game_id = game_id
        self.corpus = corpus
        self.board = chess.Board(starting_fen) if starting_fen else chess.Board()
        self.advisor = advisor or EngineAdvisor()
        self.history: List[MoveRecord] = []
        self.created_at = datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None).isoformat()

    def get_state(self) -> Dict[str, Any]:
        """Return comprehensive state of the current game."""
        legal_moves_san = [self.board.san(m) for m in self.board.legal_moves]
        legal_moves_uci = [m.uci() for m in self.board.legal_moves]
        return {
            "game_id": self.game_id,
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "move_number": self.board.fullmove_number,
            "is_game_over": self.board.is_game_over(),
            "result": self.board.result() if self.board.is_game_over() else None,
            "is_check": self.board.is_check(),
            "legal_moves_uci": legal_moves_uci,
            "legal_moves_san": legal_moves_san,
            "move_count": len(self.history),
        }

    def get_memory_insights(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant past Scenarios for the current board state."""
        matches = retrieve_relevant_scenarios(self.board, self.corpus, limit=limit)
        return [m.to_dict() for m in matches]

    def get_engine_advice(self, time_limit_secs: float = 0.5) -> Dict[str, Any]:
        """Get tactical advice from Stockfish or fallback heuristic."""
        return self.advisor.analyze_position(self.board, time_limit_secs=time_limit_secs)

    def execute_move(
        self,
        move_str: str,
        gherkin_text: str,
        explicit_origin_fen: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute move behind the mandatory Gherkin -> OKF gate.
        Checks:
        1. Gherkin is provided and non-empty.
        2. Move is legal (UCI or SAN).
        3. Gherkin parses into a valid Feature/Scenario.
        4. origin_fen matches self.board.fen().
        5. Gherkin mentions or is related to the move (san or uci).
        6. Materialization succeeds via okf-parser.
        7. Move is pushed to board.
        """
        # 1. Gherkin presence
        if not gherkin_text or not gherkin_text.strip():
            raise MissingGherkinError("Move rejected: Gherkin justification is mandatory before making a move.")

        # 2. Legality check
        try:
            # Try UCI first, then SAN
            try:
                move = chess.Move.from_uci(move_str)
                if move not in self.board.legal_moves:
                    # Maybe it was SAN
                    move = self.board.parse_san(move_str)
            except ValueError:
                move = self.board.parse_san(move_str)
        except Exception as exc:
            raise IllegalMoveError(f"Move '{move_str}' is illegal or invalid: {exc}") from exc

        if move not in self.board.legal_moves:
            raise IllegalMoveError(f"Move '{move_str}' ({move.uci()}) is not legal in current position.")

        pre_fen = self.board.fen()
        san = self.board.san(move)
        uci = move.uci()

        # 3. Gherkin parse validity
        try:
            feat = parse_gherkin(gherkin_text)
        except GherkinParseError as exc:
            raise GherkinParseError(f"Move rejected: Gherkin syntax is invalid: {exc}") from exc

        # 4. Check origin_fen
        # If user passed explicit_origin_fen or Gherkin had origin_fen tag, it must equal pre_fen
        claimed_fen = explicit_origin_fen or feat.origin_fen
        if claimed_fen and claimed_fen.strip() != pre_fen.strip():
            raise OriginMismatchError(
                f"Move rejected: Gherkin origin_fen '{claimed_fen}' does not match pre-move board state '{pre_fen}'"
            )

        # Attach pre_fen as origin_fen to feature
        feat.origin_fen = pre_fen

        # 5. Move connection check: Gherkin must mention move UCI or SAN or general tokens
        combined_text = (
            feat.name + " " + feat.description + " " +
            " ".join(sc.name + " " + " ".join(s.text for s in sc.steps) for sc in feat.scenarios)
        ).lower()

        # Relaxed matching: check if uci, san, or target square is mentioned
        target_square = chess.square_name(move.to_square)
        if not (uci.lower() in combined_text or san.lower() in combined_text or target_square in combined_text):
            raise MoveNotRelatedError(
                f"Move rejected: Gherkin explanation does not reference intended move '{uci}'/'{san}' or square '{target_square}'."
            )

        # 6. Materialize in OKF corpus
        filename = f"{self.game_id}_m{len(self.history)+1:03d}_{uci}.md"
        materialized_path = self.corpus.add_feature(feat, filename=filename)

        # Also grab insights and optional engine advice for history log
        insights = self.get_memory_insights(limit=3)

        # 7. Apply move to board
        self.board.push(move)
        post_fen = self.board.fen()

        record = MoveRecord(
            move_number=len(self.history) + 1,
            turn="white" if self.board.turn == chess.BLACK else "black",  # Color that just moved
            uci=uci,
            san=san,
            pre_fen=pre_fen,
            post_fen=post_fen,
            timestamp=datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None).isoformat(),
            gherkin=gherkin_text,
            recovered_scenarios=insights,
        )
        self.history.append(record)

        return {
            "status": "success",
            "move_uci": uci,
            "move_san": san,
            "pre_fen": pre_fen,
            "post_fen": post_fen,
            "is_game_over": self.board.is_game_over(),
            "materialized_okf_path": str(materialized_path),
            "recovered_scenarios_count": len(insights),
        }
