import json
from pathlib import Path
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from gherkin_chess.session import SessionManager

def main():
    data_dir = Path("demo_data")
    session = SessionManager(data_dir)

    rprint(Panel.fit("[bold cyan]♟ gherkin-chess Demonstration: Full Historical Consistency & READ/WRITE Loop[/bold cyan]\n"
                     "New Knowledge -> Reuse -> Explicit Divergence -> OKF Materialization"))

    # ==================== GAME 1 ====================
    rprint("\n[bold yellow]=== STARTING GAME 1 (game_001) - Initial Knowledge Creation ===[/bold yellow]")
    g1 = session.start_game("game_001")
    state = g1.get_state()
    rprint(f"Initial FEN: [green]{state['fen']}[/green]")

    # Turn 1: White e4 (NEW KNOWLEDGE)
    rprint("\n[bold]White Move 1: Creating 'Establish Central Pawn'...[/bold]")
    gherkin_e4 = """Feature: Open King Pawn
  Scenario: Establish Central Pawn
    Given starting board setup
    When white advances e4
    Then control center squares d5 and f5
"""
    res1 = g1.execute_move("e4", gherkin_text=gherkin_e4)
    rprint(f"[green]✓ Mode: {res1['epistemic_mode']}[/green] | Materialized: {res1['materialized_okf_path']}")
    rprint(f"  Origin FEN: {res1['pre_fen']}")

    # Turn 1: Black e5
    gherkin_e5 = """Feature: King Pawn Symmetry
  Scenario: Challenge White Center
    Given white has played e4
    When black counters with e5
    Then contest d4 and establish equal central space
"""
    res2 = g1.execute_move("e5", gherkin_text=gherkin_e5)

    # Turn 2: White Nf3 (NEW KNOWLEDGE: General Development)
    gherkin_nf3 = """Feature: Minor Piece Development
  Scenario: Develop Knight with Attack
    Given black pawn on e5
    When white develops knight Nf3
    Then attack e5 pawn and prepare kingside castling
"""
    res3 = g1.execute_move("Nf3", gherkin_text=gherkin_nf3)
    rprint(f"[green]✓ Mode: {res3['epistemic_mode']}[/green] | Scenario: Develop Knight with Attack")

    # ==================== GAME 2 (REUSE & DIVERGENCE) ====================
    rprint("\n[bold yellow]=== STARTING GAME 2 (game_002) - Testing Reuse & Divergence ===[/bold yellow]")
    g2 = session.start_game("game_002")

    # Turn 1: White e4 (REUSE EXISTING KNOWLEDGE)
    rprint("\n[bold]White Move 1: Reusing existing 'Establish Central Pawn'...[/bold]")
    res_reuse = g2.execute_move("e4", reuse_scenario_name="Establish Central Pawn")
    rprint(f"[green]✓ Mode: {res_reuse['epistemic_mode']}[/green] | Reused: '{res_reuse['applied_scenario']}'")
    rprint(f"  Preserved Origin FEN: {res_reuse['origin_fen']}")
    rprint(f"  Application FEN: {res_reuse['pre_fen']}")

    # Black counters with c5 (Sicilian)
    gherkin_c5 = """Feature: Sicilian Defense
  Scenario: Asymmetrical Counterplay
    Given white played e4
    When black advances c5
    Then fight for d4 without symmetrical pawn structure
"""
    g2.execute_move("c5", gherkin_text=gherkin_c5)

    # Turn 2: White Nf3 (EXPLICIT DIVERGENCE)
    rprint("\n[bold]White Move 2: Nf3 against Sicilian (Explicit Divergence from e5-attack scenario)...[/bold]")
    divergent_nf3 = """Feature: Open Sicilian Preparation
  Scenario: Prepare d4 Breakthrough
    Given black pawn on c5
    When white plays Nf3
    Then support subsequent d4 push to open lines
"""
    res_div = g2.execute_move(
        "Nf3",
        gherkin_text=divergent_nf3,
        diverges_from="Develop Knight with Attack",
        divergence_reason="In the Sicilian Defense, black has no pawn on e5; Nf3 is chosen to support the d4 breakthrough.",
    )
    rprint(f"[green]✓ Mode: {res_div['epistemic_mode']}[/green] | Diverged from: '{res_div['diverged_from']}'")
    rprint(f"  Reason: {res_div['divergence_reason']}")

    # ==================== METRICS ====================
    rprint("\n[bold yellow]=== Epistemic Corpus Metrics ===[/bold yellow]")
    metrics = session.corpus.get_application_metrics()
    table = Table(title="Knowledge Application Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    
    table.add_row("Total Decision Applications", str(metrics["total_applications"]))
    table.add_row("New Knowledge Created", str(metrics["new_knowledge_count"]))
    table.add_row("Existing Knowledge Reused", str(metrics["reused_count"]))
    table.add_row("Explicit Divergences / Refinements", str(metrics["divergence_count"]))
    rprint(table)

    rprint("\n[bold]Scenario Usage Breakdown:[/bold]")
    for sc, count in metrics["scenario_usage"].items():
        rprint(f" • [bold]{sc}[/bold]: {count} application(s)")

    rprint("\n[bold green]Demonstration Complete: Historical consistency is enforced without silent substitution.[/bold green]")

if __name__ == "__main__":
    main()