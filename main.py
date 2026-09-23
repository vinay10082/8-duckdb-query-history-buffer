"""CLI entry point for the DuckDB-backed query history buffer."""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from config import Config
from history_buffer import HistoryBuffer


def _fmt_row(row: dict) -> str:
    duration = f"{row['duration_ms']:.2f}ms" if row["duration_ms"] is not None else "-"
    return (
        f"[{row['id']}] {row['ts']} | {row['status']:<8} | {duration:<10} | "
        f"{(row['username'] or '-'):<12} | {row['query_text']}"
    )


def cmd_log(args: argparse.Namespace, buffer: HistoryBuffer) -> None:
    record_id = buffer.log(
        query_text=args.query,
        status=args.status,
        duration_ms=args.duration_ms,
        rows_affected=args.rows_affected,
        source=args.source,
        username=args.username,
        error_message=args.error_message,
    )
    print(f"Logged history record id={record_id}")


def cmd_list(args: argparse.Namespace, buffer: HistoryBuffer) -> None:
    since = None
    if args.since_hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)

    rows = buffer.list(
        limit=args.limit,
        status=args.status,
        username=args.username,
        since=since,
        search=args.search,
    )
    if not rows:
        print("No history records found.")
        return
    for row in rows:
        print(_fmt_row(row))


def cmd_stats(args: argparse.Namespace, buffer: HistoryBuffer) -> None:
    stats = buffer.stats()
    print(f"Total records : {stats['total_records']}")
    avg = stats["avg_duration_ms"]
    p95 = stats["p95_duration_ms"]
    print(f"Avg duration  : {avg:.2f}ms" if avg is not None else "Avg duration  : n/a")
    print(f"P95 duration  : {p95:.2f}ms" if p95 is not None else "P95 duration  : n/a")
    print(f"Error count   : {stats['error_count']}")

    if stats["by_status"]:
        print("\nBy status:")
        for entry in stats["by_status"]:
            print(f"  {entry['status']:<10} {entry['count']}")

    if stats["slowest_queries"]:
        print("\nSlowest queries:")
        for q in stats["slowest_queries"]:
            print(f"  [{q['id']}] {q['duration_ms']:.2f}ms | {q['query_text']}")


def cmd_purge(args: argparse.Namespace, buffer: HistoryBuffer) -> None:
    removed = buffer.purge(retention_days=args.days)
    print(f"Purged {removed} record(s).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Durable analytical buffer for tracking and querying historical system interactions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    log_parser = subparsers.add_parser("log", help="Record a new query history entry")
    log_parser.add_argument("query", help="The query text to record")
    log_parser.add_argument("--status", default="success", help="Execution status (default: success)")
    log_parser.add_argument("--duration-ms", type=float, default=None, help="Execution duration in milliseconds")
    log_parser.add_argument("--rows-affected", type=int, default=None, help="Number of rows affected")
    log_parser.add_argument("--source", default=None, help="Source system or component")
    log_parser.add_argument("--username", default=None, help="User who issued the query")
    log_parser.add_argument("--error-message", default=None, help="Error message, if any")
    log_parser.set_defaults(func=cmd_log)

    list_parser = subparsers.add_parser("list", help="List recent query history entries")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum number of records to show")
    list_parser.add_argument("--status", default=None, help="Filter by status")
    list_parser.add_argument("--username", default=None, help="Filter by username")
    list_parser.add_argument("--since-hours", type=float, default=None, help="Only show records from the last N hours")
    list_parser.add_argument("--search", default=None, help="Filter by substring match on query text")
    list_parser.set_defaults(func=cmd_list)

    stats_parser = subparsers.add_parser("stats", help="Show aggregate statistics over the history buffer")
    stats_parser.set_defaults(func=cmd_stats)

    purge_parser = subparsers.add_parser("purge", help="Remove records older than the retention window")
    purge_parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override retention window in days (defaults to MAX_HISTORY_RETENTION_DAYS)",
    )
    purge_parser.set_defaults(func=cmd_purge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config.from_env()
    with HistoryBuffer(config) as buffer:
        args.func(args, buffer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
