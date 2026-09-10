from pathlib import Path
from gherkin_chess.leaderboard import LeaderboardManager


def test_openskill_ladder(tmp_path):
    lb = LeaderboardManager(tmp_path / "leaderboard.json")
    
    # 2 jogadores iniciais
    lb.record_match(
        player_white="Model-A (MCP)",
        player_black="Model-B (Raw)",
        model_white="openrouter/meta-llama/llama-3.3-70b-instruct",
        model_black="openrouter/meta-llama/llama-3.1-8b-instruct",
        outcome="white",
        game_id="g1",
        plies=30,
    )

    standings = lb.get_standings()
    assert len(standings) == 2
    assert standings[0]["name"] == "Model-A (MCP)"
    assert standings[0]["wins"] == 1
    assert standings[1]["name"] == "Model-B (Raw)"
    assert standings[1]["losses"] == 1
    assert standings[0]["ordinal"] > standings[1]["ordinal"]


def test_persistence_of_leaderboard(tmp_path):
    file_path = tmp_path / "lb.json"
    lb1 = LeaderboardManager(file_path)
    lb1.record_match("P1", "P2", "m1", "m2", "draw", "g1", 20)
    
    # Recarrega de novo objeto
    lb2 = LeaderboardManager(file_path)
    standings = lb2.get_standings()
    assert len(standings) == 2
    assert standings[0]["draws"] == 1