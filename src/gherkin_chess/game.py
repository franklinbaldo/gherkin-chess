from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    """Raised when a move is attempted without providing Gherkin or reuse reference."""
    pass


class OriginMismatchError(ValueError):
    """Raised when the Gherkin's origin_fen does not match the pre-move board state."""
    pass


class MoveNotRelatedError(ValueError):
    """Raised when the Gherkin explanation has no connection to the intended move."""
    pass


class SilentSubstitutionError(ValueError):
    """
    Raised when a move has relevant matching scenarios in memory, but the agent
    submits a new competing Gherkin without either reusing the scenario or
    explicitly declaring and explaining the divergence.
    """
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
    epistemic_mode: str  # 'new' | 'reuse' | 'divergence'
    applied_scenario: Optional[str] = None
    origin_fen: Optional[str] = None
    diverged_from: Optional[str] = None
    divergence_reason: Optional[str] = None
    recovered_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    engine_advice: Optional[Dict[str, Any]] = None


class ChessGame:
    """
    Manages a single game session, enforcing:
    1. Legality of chess moves.
    2. Mandatory Gherkin justification before move execution (new, reuse, or divergence).
    3. Non-silent substitution: historical consistency requirement.
    4. Exact origin_fen match (the FEN right before the move for new/diverged Gherkin).
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
        self.created_at = datetime.now(timezone.utc).isoformat()

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

    def get_memory_insights(self, candidate_move: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant past Scenarios for the current board state and candidate move."""
        matches = retrieve_relevant_scenarios(self.board, self.corpus, candidate_move=candidate_move, limit=limit)
        return [m.to_dict() for m in matches]

    def get_engine_advice(self, time_limit_secs: float = 0.5) -> Dict[str, Any]:
        """Get tactical advice from Stockfish or fallback heuristic."""
        return self.advisor.analyze_position(self.board, time_limit_secs=time_limit_secs)

    def execute_direct_move(self, move_str: str) -> Dict[str, Any]:
        """
        Execute a legal move directly without requiring Gherkin or OKF materialization.
        Used by the standard/raw agent variant playing through MCP.
        """
        try:
            try:
                move = chess.Move.from_uci(move_str)
                if move not in self.board.legal_moves:
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

        self.board.push(move)
        post_fen = self.board.fen()

        record = MoveRecord(
            move_number=len(self.history) + 1,
            turn="white" if self.board.turn == chess.BLACK else "black",
            uci=uci,
            san=san,
            pre_fen=pre_fen,
            post_fen=post_fen,
            timestamp=datetime.now(timezone.utc).isoformat(),
            gherkin="",
            epistemic_mode="direct_mcp",
            applied_scenario=None,
            origin_fen=None,
            diverged_from=None,
            divergence_reason=None,
            recovered_scenarios=[],
        )
        self.history.append(record)

        return {
            "status": "success",
            "move_uci": uci,
            "move_san": san,
            "pre_fen": pre_fen,
            "post_fen": post_fen,
            "epistemic_mode": "direct_mcp",
            "is_game_over": self.board.is_game_over(),
        }

    def execute_move(
        self,
        move_str: str,
        gherkin_text: Optional[str] = None,
        reuse_scenario_name: Optional[str] = None,
        diverges_from: Optional[str] = None,
        divergence_reason: Optional[str] = None,
        explicit_origin_fen: Optional[str] = None,
        enforce_non_silent_substitution: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute move behind the mandatory Gherkin -> OKF gate with historical consistency.
        Modes:
        A. REUSE: reuse_scenario_name is provided. Uses existing scenario without duplicating OKF.
        B. DIVERGENCE: new gherkin provided + diverges_from + divergence_reason.
        C. NEW: new gherkin provided. If enforce_non_silent_substitution is True and a strong match exists,
           raises SilentSubstitutionError requiring the agent to either reuse or diverge.
        """
        # 1. Parse move and legality
        try:
            try:
                move = chess.Move.from_uci(move_str)
                if move not in self.board.legal_moves:
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

        # Check existing memory for this move / position
        insights = self.get_memory_insights(candidate_move=san, limit=3)

        epistemic_mode = "new"
        applied_sc_name = None
        origin_fen_recorded = None
        materialized_path = None
        final_gherkin_text = ""

        # MODE A: REUSE EXISTING SCENARIO
        if reuse_scenario_name:
            found = self.corpus.find_scenario(reuse_scenario_name)
            if not found:
                raise ValueError(f"Scenario '{reuse_scenario_name}' requested for reuse was not found in corpus.")
            sc, feat = found
            epistemic_mode = "reuse"
            applied_sc_name = sc.name
            origin_fen_recorded = feat.origin_fen
            final_gherkin_text = sc.to_gherkin()

            # Record application in corpus
            self.corpus.record_application(
                scenario_name=sc.name,
                origin_fen=feat.origin_fen or "unknown",
                application_fen=pre_fen,
                move=san,
                game_id=self.game_id,
                epistemic_mode="reuse",
            )

        # MODE B or C: NEW GHERKIN SUBMITTED
        else:
            if not gherkin_text or not gherkin_text.strip():
                raise MissingGherkinError("Move rejected: Gherkin justification or reuse_scenario_name is mandatory.")

            # Check non-silent substitution if enforced
            if enforce_non_silent_substitution and not diverges_from:
                strong_matches = [m for m in insights if m["score"] >= 0.7]
                if strong_matches:
                    matching_sc = strong_matches[0]["scenario_name"]
                    raise SilentSubstitutionError(
                        f"Move rejected: A relevant scenario '{matching_sc}' already exists for this context. "
                        f"You must either reuse it via reuse_scenario_name='{matching_sc}', or explicitly declare "
                        f"diverges_from='{matching_sc}' and explain why via divergence_reason."
                    )

            # Parse Gherkin syntax
            try:
                feat = parse_gherkin(gherkin_text)
            except GherkinParseError as exc:
                raise GherkinParseError(f"Move rejected: Gherkin syntax is invalid: {exc}") from exc

            # Verify origin_fen
            claimed_fen = explicit_origin_fen or feat.origin_fen
            if claimed_fen and claimed_fen.strip() != pre_fen.strip():
                raise OriginMismatchError(
                    f"Move rejected: Gherkin origin_fen '{claimed_fen}' does not match pre-move board state '{pre_fen}'"
                )

            feat.origin_fen = pre_fen
            origin_fen_recorded = pre_fen

            # Verify reference to move
            combined_text = (
                feat.name + " " + feat.description + " " +
                " ".join(sc.name + " " + " ".join(s.text for s in sc.steps) for sc in feat.scenarios)
            ).lower()
            target_square = chess.square_name(move.to_square)
            if not (uci.lower() in combined_text or san.lower() in combined_text or target_square in combined_text):
                raise MoveNotRelatedError(
                    f"Move rejected: Gherkin explanation does not reference intended move '{uci}'/'{san}' or square '{target_square}'."
                )

            # If divergence, tag the feature with provenance
            if diverges_from:
                epistemic_mode = "divergence"
                div_clean = diverges_from.replace(" ", "_")
                reason_clean = (divergence_reason or "unspecified").replace(" ", "_")[:80]
                feat.tags.extend([
                    f"diverges_from:{div_clean}",
                    f"divergence_reason:{reason_clean}",
                    "relation:refines",
                ])

            # Materialize in OKF
            filename = f"{self.game_id}_m{len(self.history)+1:03d}_{uci}.md"
            materialized_path = str(self.corpus.add_feature(feat, filename=filename))
            final_gherkin_text = feat.to_gherkin()

            # Record application in history
            main_sc = feat.scenarios[0].name if feat.scenarios else feat.name
            applied_sc_name = main_sc
            self.corpus.record_application(
                scenario_name=main_sc,
                origin_fen=pre_fen,
                application_fen=pre_fen,
                move=san,
                game_id=self.game_id,
                epistemic_mode=epistemic_mode,
                diverged_from=diverges_from,
                divergence_reason=divergence_reason,
            )

        # Apply move to board
        self.board.push(move)
        post_fen = self.board.fen()

        record = MoveRecord(
            move_number=len(self.history) + 1,
            turn="white" if self.board.turn == chess.BLACK else "black",
            uci=uci,
            san=san,
            pre_fen=pre_fen,
            post_fen=post_fen,
            timestamp=datetime.now(timezone.utc).isoformat(),
            gherkin=final_gherkin_text,
            epistemic_mode=epistemic_mode,
            applied_scenario=applied_sc_name,
            origin_fen=origin_fen_recorded,
            diverged_from=diverges_from,
            divergence_reason=divergence_reason,
            recovered_scenarios=insights,
        )
        self.history.append(record)

        return {
            "status": "success",
            "move_uci": uci,
            "move_san": san,
            "pre_fen": pre_fen,
            "post_fen": post_fen,
            "epistemic_mode": epistemic_mode,
            "applied_scenario": applied_sc_name,
            "origin_fen": origin_fen_recorded,
            "diverged_from": diverges_from,
            "divergence_reason": divergence_reason,
            "is_game_over": self.board.is_game_over(),
            "materialized_okf_path": str(materialized_path) if materialized_path else None,
            "recovered_scenarios_count": len(insights),
        }