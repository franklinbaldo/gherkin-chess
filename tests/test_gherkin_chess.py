import pytest
from pathlib import Path
import chess

from gherkin_chess.parser import parse_gherkin, GherkinParseError
from gherkin_chess.materializer import materialize_feature
from gherkin_chess.corpus import CorpusManager
from gherkin_chess.game import (
    ChessGame,
    IllegalMoveError,
    MissingGherkinError,
    OriginMismatchError,
    MoveNotRelatedError,
)
from gherkin_chess.retrieval import retrieve_relevant_scenarios


@pytest.fixture
def tmp_corpus(tmp_path):
    return CorpusManager(tmp_path / "corpus")


def test_parser_and_roundtrip():
    gherkin_text = """@origin_fen:rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR_w_KQkq_-_0_1
Feature: Opening Principles
  Scenario: Advance Central Pawn
    Given the initial board setup
    When white moves e4
    Then control the center squares d5 and f5
"""
    feat = parse_gherkin(gherkin_text)
    assert feat.name == "Opening Principles"
    assert len(feat.scenarios) == 1
    assert feat.scenarios[0].name == "Advance Central Pawn"
    assert len(feat.scenarios[0].steps) == 3
    assert feat.origin_fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    # Reversibility test
    rt = feat.to_gherkin()
    assert "Feature: Opening Principles" in rt
    assert "Scenario: Advance Central Pawn" in rt
    assert "Given the initial board setup" in rt


def test_materialization_with_real_okf_parser(tmp_path):
    gherkin_text = """Feature: Center Dominance
  Scenario: Control Center With e4
    Given board at start
    When white plays e4
    Then establish outpost
"""
    feat = parse_gherkin(gherkin_text)
    feat.origin_fen = chess.STARTING_FEN
    mat_file = materialize_feature(feat, tmp_path / "features")
    assert mat_file.exists()

    # Load bundle via CorpusManager and okf-parser
    corpus = CorpusManager(tmp_path)
    bundle = corpus.get_bundle()
    assert bundle.concepts.count().execute() == 1


def test_gate_rejects_missing_gherkin(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    with pytest.raises(MissingGherkinError):
        game.execute_move("e4", "")


def test_gate_rejects_invalid_gherkin(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    with pytest.raises(GherkinParseError):
        game.execute_move("e4", "This is not valid Gherkin syntax at all")


def test_gate_rejects_illegal_move(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    valid_gherkin = """Feature: Impossible Move
  Scenario: Jumping across the board
    Given initial setup
    When white plays e5
    Then jump
"""
    with pytest.raises(IllegalMoveError):
        game.execute_move("e5", valid_gherkin)


def test_gate_rejects_origin_fen_mismatch(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    fake_fen = "8/8/8/8/8/8/8/4K2k w - - 0 1"
    gherkin = f"""@origin_fen:{fake_fen.replace(' ', '_')}
Feature: Spoofed Origin
  Scenario: Play e4 with fake origin
    Given fake board
    When white plays e4
    Then center
"""
    with pytest.raises(OriginMismatchError):
        game.execute_move("e4", gherkin)


def test_gate_rejects_unrelated_gherkin(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    unrelated_gherkin = """Feature: Rook Movement
  Scenario: Castle Queen Side
    Given rook on a1
    When consider a3
    Then nothing
"""
    with pytest.raises(MoveNotRelatedError):
        game.execute_move("e4", unrelated_gherkin)


def test_successful_move_materialization_and_origin_fen(tmp_corpus):
    game = ChessGame(game_id="g1", corpus=tmp_corpus)
    start_fen = game.board.fen()

    valid_gherkin = """Feature: First Move
  Scenario: Occupy center
    Given starting position
    When white plays e4
    Then occupy center
"""
    res = game.execute_move("e4", valid_gherkin)
    assert res["status"] == "success"
    assert res["pre_fen"] == start_fen
    assert game.board.piece_at(chess.E4) is not None
    assert Path(res["materialized_okf_path"]).exists()

    # Verify origin_fen was preserved in corpus
    features = tmp_corpus.load_all_features()
    assert len(features) == 1
    assert features[0].origin_fen == start_fen


def test_read_write_loop_and_persistence(tmp_corpus):
    # Game 1: play e4 and e5
    g1 = ChessGame(game_id="game_1", corpus=tmp_corpus)
    g1.execute_move("e4", """Feature: Opening
  Scenario: Kings Pawn
    Given start
    When white plays e4
    Then control center
""")
    g1.execute_move("e5", """Feature: Response
  Scenario: Black Kings Pawn
    Given after e4
    When black plays e5
    Then contest center
""")

    # Game 2: Brand new session with same persistent corpus
    g2 = ChessGame(game_id="game_2", corpus=tmp_corpus)
    insights = g2.get_memory_insights(limit=5)
    assert len(insights) >= 1
    # Check that Kings Pawn scenario was retrieved because of starting position similarity
    assert any("Kings Pawn" in item["scenario_name"] for item in insights)