import json
from pathlib import Path
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from gherkin_chess.session import SessionManager

def main():
    data_dir = Path("demo_data")
    session = SessionManager(data_dir)

    rprint(Panel.fit("[bold cyan]♟ gherkin-chess Demonstration: Full READ/WRITE Loop[/bold cyan]\n"
                     "Move Gate -> Gherkin Formulation -> okf-parser Materialization -> Execution"))

    # ==================== GAME 1 ====================
    rprint("\n[bold yellow]=== STARTING GAME 1 (game_001) ===[/bold yellow]")
    g1 = session.start_game("game_001")
    state = g1.get_state()
    rprint(f"Initial FEN: [green]{state['fen']}[/green]")

    # Turn 1: White e4
    rprint("\n[bold]White deliberates on move 1...[/bold]")
    advice = g1.get_engine_advice()
    rprint(f"Engine Advisor suggests: [cyan]{advice['best_move']}[/cyan] (Eval: {advice['evaluation_cp']})")
    
    gherkin_e4 = """Feature: Open King Pawn
  Scenario: Establish Central Pawn
    Given starting board setup
    When white advances e4
    Then control center squares d5 and f5
"""
    rprint("Submitting move 'e4' with Gherkin...")
    res1 = g1.execute_move("e4", gherkin_e4)
    rprint(f"[green]✓ Move e4 executed successfully![/green] Materialized in OKF: {res1['materialized_okf_path']}")
    rprint(f"Origin FEN saved: {res1['pre_fen']}")

    # Turn 1: Black e5
    rprint("\n[bold]Black deliberates on response...[/bold]")
    gherkin_e5 = """Feature: King Pawn Symmetry
  Scenario: Challenge White Center
    Given white has played e4
    When black counters with e5
    Then contest d4 and establish equal central space
"""
    res2 = g1.execute_move("e5", gherkin_e5)
    rprint(f"[green]✓ Move e5 executed successfully![/green] Materialized in OKF: {res2['materialized_okf_path']}")

    # Turn 2: White Nf3
    rprint("\n[bold]White deliberates on move 2...[/bold]")
    mem1 = g1.get_memory_insights()
    rprint(f"Operational Memory Recovered: [magenta]{len(mem1)} scenarios[/magenta]")
    for m in mem1:
        rprint(f" - [bold]{m['scenario_name']}[/bold] (score: {m['score']}) from origin: {m['origin_fen']}")

    gherkin_nf3 = """Feature: Minor Piece Development
  Scenario: Develop Knight with Attack
    Given black pawn on e5
    When white develops knight Nf3
    Then attack e5 pawn and prepare kingside castling
"""
    res3 = g1.execute_move("Nf3", gherkin_nf3)
    rprint(f"[green]✓ Move Nf3 executed successfully![/green]")

    # Turn 2: Black Nc6
    gherkin_nc6 = """Feature: Piece Defense
  Scenario: Defend e5 Pawn
    Given white knight attacks e5
    When black develops Nc6
    Then protect e5 while developing queenside minor piece
"""
    res4 = g1.execute_move("Nc6", gherkin_nc6)
    rprint(f"[green]✓ Move Nc6 executed successfully![/green]")

    # ==================== GAME 2 (REUSE DEMO) ====================
    rprint("\n[bold yellow]=== STARTING GAME 2 (game_002) - Testing Memory Retrieval ===[/bold yellow]")
    g2 = session.start_game("game_002")
    rprint("Brand new game initiated. Querying operational memory for the initial position...")
    
    recovered = g2.get_memory_insights(limit=5)
    
    table = Table(title="Retrieved Scenarios from OKF Corpus for Game 2 Move 1")
    table.add_column("Scenario", style="cyan")
    table.add_column("Feature", style="magenta")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Origin FEN", style="dim")
    
    for rec in recovered:
        table.add_row(rec["scenario_name"], rec["feature_name"], str(rec["score"]), rec["origin_fen"])
    
    rprint(table)
    
    rprint("\n[bold green]Demonstration Complete: The READ/WRITE cycle functions end-to-end with true OKF materialization.[/bold green]")

if __name__ == "__main__":
    main()