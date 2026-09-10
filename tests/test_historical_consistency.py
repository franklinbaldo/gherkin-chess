import pytest
from pathlib import Path
import chess

from gherkin_chess.game import (
    ChessGame,
    SilentSubstitutionError,
)
from gherkin_chess.corpus import CorpusManager


@pytest.fixture
def corpus(tmp_path):
    return CorpusManager(tmp_path / "corpus")


def test_reuse_existing_scenario(corpus):
    # Setup initial rule
    g1 = ChessGame(game_id="game_1", corpus=corpus)
    p1 = g1.board.fen()
    g1.execute_move("e4", """Feature: Open King Pawn
  Scenario: Establish Central Pawn
    Given initial board setup
    When white plays e4
    Then control center
""")

    # Game 2: In the same opening position, reuse the existing scenario
    g2 = ChessGame(game_id="game_2", corpus=corpus)
    p2 = g2.board.fen()
    assert p1 == p2

    res = g2.execute_move("e4", reuse_scenario_name="Establish Central Pawn")
    assert res["status"] == "success"
    assert res["epistemic_mode"] == "reuse"
    assert res["applied_scenario"] == "Establish Central Pawn"
    assert res["origin_fen"] == p1  # Immutable origin preserved
    assert g2.board.piece_at(chess.E4) is not None

    # Check metrics
    metrics = corpus.get_application_metrics()
    assert metrics["total_applications"] == 2
    assert metrics["new_knowledge_count"] == 1
    assert metrics["reused_count"] == 1
    assert metrics["scenario_usage"]["Establish Central Pawn"] == 2


def test_divergence_from_existing_scenario(corpus):
    # Initial rule for Nf3 (development)
    g1 = ChessGame(game_id="game_1", corpus=corpus)
    g1.execute_move("e4", """Feature: Initial Move
  Scenario: e4
    Given start
    When white plays e4
    Then center
""")
    g1.execute_move("e5", """Feature: Defense
  Scenario: e5
    Given e4
    When black plays e5
    Then respond
""")
    g1.execute_move("Nf3", """Feature: Development
  Scenario: Develop Knight
    Given minor piece on g1
    When white plays Nf3
    Then develop piece towards center
""")

    # In Game 2, white plays Nf3 not for development, but for tactical reason
    g2 = ChessGame(game_id="game_2", corpus=corpus)
    g2.execute_move("e4", reuse_scenario_name="e4")
    g2.execute_move("e5", reuse_scenario_name="e5")
    
    divergent_gherkin = """Feature: Tactical King Knight
  Scenario: Attack e5 Directly
    Given black e5 pawn is undefended
    When white plays Nf3
    Then apply concrete tactical pressure on e5
"""
    res = g2.execute_move(
        "Nf3",
        gherkin_text=divergent_gherkin,
        diverges_from="Develop Knight",
        divergence_reason="In this position, Nf3 is chosen primarily for immediate attack on undefended e5, not general development.",
    )
    assert res["status"] == "success"
    assert res["epistemic_mode"] == "divergence"
    assert res["applied_scenario"] == "Attack e5 Directly"

    metrics = corpus.get_application_metrics()
    assert metrics["divergence_count"] == 1


def test_reject_silent_substitution_when_enforced(corpus):
    # Setup initial rule
    g1 = ChessGame(game_id="game_1", corpus=corpus)
    g1.execute_move("e4", """Feature: Open King Pawn
  Scenario: Establish Central Pawn
    Given initial board setup
    When white plays e4
    Then control center
""")

    # Game 2: Attempt to play e4 with a brand new Gherkin without acknowledging the prior rule
    g2 = ChessGame(game_id="game_2", corpus=corpus)
    competing_gherkin = """Feature: Alternative Pawn Move
  Scenario: Move Pawn Forward
    Given start
    When white plays e4
    Then move forward
"""
    with pytest.raises(SilentSubstitutionError) as exc_info:
        g2.execute_move(
            "e4",
            gherkin_text=competing_gherkin,
            enforce_non_silent_substitution=True,
        )
    assert "Establish Central Pawn" in str(exc_info.value)