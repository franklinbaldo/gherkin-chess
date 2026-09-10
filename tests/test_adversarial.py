import pytest
from pathlib import Path
import chess

from gherkin_chess.game import (
    ChessGame,
    IllegalMoveError,
    MissingGherkinError,
    OriginMismatchError,
    MoveNotRelatedError,
)
from gherkin_chess.parser import GherkinParseError
from gherkin_chess.corpus import CorpusManager
from gherkin_chess.engine_advisor import EngineAdvisor


@pytest.fixture
def clean_corpus(tmp_path):
    return CorpusManager(tmp_path / "corpus")


def test_adversarial_empty_gherkin(clean_corpus):
    game = ChessGame(game_id="adv_1", corpus=clean_corpus)
    with pytest.raises(MissingGherkinError):
        game.execute_move("e4", "   \n\t  ")


def test_adversarial_malformed_syntax(clean_corpus):
    game = ChessGame(game_id="adv_1", corpus=clean_corpus)
    with pytest.raises(GherkinParseError):
        game.execute_move("e4", "Feature without title or steps\nsomething random\n")


def test_adversarial_unrelated_content(clean_corpus):
    game = ChessGame(game_id="adv_1", corpus=clean_corpus)
    with pytest.raises(MoveNotRelatedError):
        game.execute_move("Nf3", """Feature: Wrong Move
  Scenario: Talking about queenside
    Given board at start
    When white plays c4
    Then claim english opening
""")


def test_adversarial_origin_spoofing(clean_corpus):
    game = ChessGame(game_id="adv_1", corpus=clean_corpus)
    tampered_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    gherkin = f"""@origin_fen:{tampered_fen.replace(' ', '_')}
Feature: Spoofed FEN
  Scenario: Knight out
    Given tampered position
    When white plays Nf3
    Then attack e5
"""
    with pytest.raises(OriginMismatchError):
        game.execute_move("Nf3", gherkin)


def test_adversarial_stockfish_bypass_attempt(clean_corpus):
    """
    Ensure that engine advisor advice CANNOT bypass the Gherkin gate.
    Even when engine recommends best move, execute_move still demands Gherkin.
    """
    advisor = EngineAdvisor()
    game = ChessGame(game_id="adv_1", corpus=clean_corpus, advisor=advisor)
    advice = game.get_engine_advice()
    best_move = advice["best_move"]
    assert best_move is not None

    # Trying to play best_move without Gherkin must fail
    with pytest.raises(MissingGherkinError):
        game.execute_move(best_move, "")


def test_adversarial_origin_fen_immutability(clean_corpus):
    """Ensure an established feature's origin_fen cannot be silently mutated."""
    game = ChessGame(game_id="adv_1", corpus=clean_corpus)
    p1 = game.board.fen()
    game.execute_move("e4", """Feature: Move 1
  Scenario: e4
    Given start
    When white plays e4
    Then center
""")
    features = clean_corpus.load_all_features()
    assert features[0].origin_fen == p1

    # Black moves e5
    p2 = game.board.fen()
    game.execute_move("e5", """Feature: Move 2
  Scenario: e5
    Given e4 on board
    When black plays e5
    Then contest
""")
    features = clean_corpus.load_all_features()
    # First feature still has p1, second has p2
    assert features[0].origin_fen == p1
    assert features[1].origin_fen == p2