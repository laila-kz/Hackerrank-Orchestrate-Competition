#!/usr/bin/env python3
"""
CLI Application for Multi-Domain Support Ticket Triage.

Usage:
    python code/main.py [--input TICKETS_CSV] [--output OUTPUT_CSV] [--reindex] [--interactive]
"""

import argparse
import csv
import sys
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
    )
    from rich.table import Table
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from agent import SupportAgent

# Setup console theme
if HAS_RICH:
    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "accent": "magenta"
    })
    console = Console(theme=custom_theme)
else:
    console = None


def print_banner():
    """Display CLI Header Banner."""
    banner_text = (
        "[bold cyan]HackerRank Orchestrate — Multi-Domain Support Triage Agent[/bold cyan]\n"
        "[dim]Ecosystems: HackerRank | Claude | Visa | General Support[/dim]"
    )
    if HAS_RICH:
        console.print(Panel(banner_text, border_style="cyan", expand=False))
    else:
        print("================================================================")
        print(" HackerRank Orchestrate — Multi-Domain Support Triage Agent")
        print(" Ecosystems: HackerRank | Claude | Visa | General Support")
        print("================================================================")


def process_tickets_batch(agent: SupportAgent, input_path: Path, output_path: Path):
    """Run batch triage over input CSV file and write results."""
    if not input_path.exists():
        msg = f"Error: Input file '{input_path}' does not exist!"
        if HAS_RICH:
            console.print(f"[error]{msg}[/error]")
        else:
            print(msg)
        sys.exit(1)

    tickets: list[dict[str, str]]
    with open(input_path, "r", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))

    total_tickets = len(tickets)
    if HAS_RICH:
        console.print(f"\n[info]Loaded {total_tickets} tickets from '{input_path.name}'[/info]")
        console.print("[info]Initializing vector retrieval & triage pipeline...[/info]\n")
    else:
        print(f"\nLoaded {total_tickets} tickets from '{input_path}'")
        print("Processing tickets...\n")

    results: list[dict[str, str]] = []
    stats = {
        "replied": 0,
        "escalated": 0,
        "request_types": {"product_issue": 0, "feature_request": 0, "bug": 0, "invalid": 0}
    }

    start_time = time.time()

    if HAS_RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Triaging support tickets...", total=total_tickets)

            for i, ticket in enumerate(tickets, 1):
                issue = ticket.get("Issue", ticket.get("issue", ""))
                subject = ticket.get("Subject", ticket.get("subject", ""))
                company = ticket.get("Company", ticket.get("company", "None"))

                res = agent.process_ticket(issue=issue, subject=subject, company=company)

                # Track stats
                status = res.get("status", "replied")
                req_type = res.get("request_type", "product_issue")

                stats[status] = stats.get(status, 0) + 1
                stats["request_types"][req_type] = stats["request_types"].get(req_type, 0) + 1

                results.append({
                    "issue": issue,
                    "subject": subject,
                    "company": company,
                    "response": res.get("response", ""),
                    "product_area": res.get("product_area", "general_support"),
                    "status": status,
                    "request_type": req_type,
                    "justification": res.get("justification", ""),
                })

                progress.update(task, advance=1)
    else:
        for i, ticket in enumerate(tickets, 1):
            issue = ticket.get("Issue", ticket.get("issue", ""))
            subject = ticket.get("Subject", ticket.get("subject", ""))
            company = ticket.get("Company", ticket.get("company", "None"))

            res = agent.process_ticket(issue=issue, subject=subject, company=company)

            status = res.get("status", "replied")
            req_type = res.get("request_type", "product_issue")

            stats[status] = stats.get(status, 0) + 1
            stats["request_types"][req_type] = stats["request_types"].get(req_type, 0) + 1

            results.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "response": res.get("response", ""),
                "product_area": res.get("product_area", "general_support"),
                "status": status,
                "request_type": req_type,
                "justification": res.get("justification", ""),
            })
            print(f"[{i}/{total_tickets}] Processed: {status.upper()} | Type: {req_type}")

    elapsed = round(time.time() - start_time, 2)

    # Ensure output parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output CSV matching standard evaluation schema
    fieldnames = ["issue", "subject", "company", "response", "product_area", "status", "request_type", "justification"]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Display Summary Table
    if HAS_RICH:
        table = Table(title="Triage Execution Summary", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("Value", style="bold green")

        table.add_row("Total Tickets Processed", str(total_tickets))
        table.add_row("Status: Replied", f"[green]{stats['replied']}[/green]")
        table.add_row("Status: Escalated", f"[yellow]{stats['escalated']}[/yellow]")
        table.add_row("Request Type: Product Issue", str(stats["request_types"]["product_issue"]))
        table.add_row("Request Type: Feature Request", str(stats["request_types"]["feature_request"]))
        table.add_row("Request Type: Bug", str(stats["request_types"]["bug"]))
        table.add_row("Request Type: Invalid", str(stats["request_types"]["invalid"]))
        table.add_row("Elapsed Execution Time", f"{elapsed}s")

        console.print("\n")
        console.print(table)
        console.print(f"\n[success][SUCCESS] Batch execution complete! Output saved to: '{output_path}'[/success]\n")
    else:
        print("\n=== Execution Summary ===")
        print(f"Total Processed: {total_tickets}")
        print(f"Replied: {stats['replied']} | Escalated: {stats['escalated']}")
        print(f"Time Taken: {elapsed}s")
        print(f"Output saved to: {output_path}")


def run_interactive(agent: SupportAgent):
    """Run interactive mode for ad-hoc ticket testing."""
    if HAS_RICH:
        console.print(Panel("[bold yellow]Interactive Triage Mode[/bold yellow]\nType 'exit' or 'quit' to end session.", border_style="yellow"))
    else:
        print("\n--- Interactive Triage Mode ---")

    while True:
        try:
            if HAS_RICH:
                issue = console.input("[bold cyan]\nEnter Issue Description: [/bold cyan]").strip()
            else:
                issue = input("\nEnter Issue Description: ").strip()

            if issue.lower() in ["exit", "quit"]:
                break
            if not issue:
                continue

            if HAS_RICH:
                company = console.input("[bold cyan]Company (HackerRank/Claude/Visa/None) [None]: [/bold cyan]").strip() or "None"
                subject = console.input("[bold cyan]Subject (optional): [/bold cyan]").strip()
            else:
                company = input("Company (HackerRank/Claude/Visa/None) [None]: ").strip() or "None"
                subject = input("Subject (optional): ").strip()

            result = agent.process_ticket(issue=issue, subject=subject, company=company)

            if HAS_RICH:
                res_table = Table(title="Triage Result", border_style="green")
                res_table.add_column("Field", style="bold white")
                res_table.add_column("Value", style="cyan")

                res_table.add_row("Status", f"[bold {'green' if result['status']=='replied' else 'yellow'}]{result['status'].upper()}[/bold]")
                res_table.add_row("Product Area", result["product_area"])
                res_table.add_row("Request Type", result["request_type"])
                res_table.add_row("Justification", result["justification"])
                res_table.add_row("Response", result["response"])

                console.print(res_table)
            else:
                print("\n--- Triage Result ---")
                for k, v in result.items():
                    print(f"{k.upper()}: {v}")

        except KeyboardInterrupt:
            break

    if HAS_RICH:
        console.print("[yellow]Exiting interactive session.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="HackerRank Orchestrate Support Triage Agent")
    parser.add_argument("--input", type=str, default=None, help="Path to input support tickets CSV")
    parser.add_argument("--output", type=str, default=None, help="Path to output predictions CSV")
    parser.add_argument("--data", type=str, default=None, help="Path to support documents folder")
    parser.add_argument("--reindex", action="store_true", help="Force rebuild ChromaDB vector database index")
    parser.add_argument("--interactive", action="store_true", help="Run interactive single ticket triage CLI")

    args = parser.parse_args()

    print_banner()

    # Determine default paths relative to workspace
    base_dir = Path(__file__).resolve().parent
    repo_root = (base_dir / "..").resolve()

    input_path = Path(args.input).resolve() if args.input else (repo_root / "support_tickets/support_tickets.csv").resolve()
    output_path = Path(args.output).resolve() if args.output else (repo_root / "support_tickets/output.csv").resolve()
    data_path = Path(args.data).resolve() if args.data else (repo_root / "data").resolve()

    if HAS_RICH:
        console.print(f"[dim]Repo Root: {repo_root}[/dim]")
        console.print(f"[dim]Data Path: {data_path}[/dim]\n")

    # Initialize Agent
    agent = SupportAgent(data_path=str(data_path))

    if args.reindex:
        if HAS_RICH:
            console.print("[warning]Reindexing vector database...[/warning]")
        agent.retriever._initialize_or_load(force_reindex=True)

    if args.interactive:
        run_interactive(agent)
    else:
        process_tickets_batch(agent=agent, input_path=input_path, output_path=output_path)


if __name__ == "__main__":
    main()