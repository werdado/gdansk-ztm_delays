"""Polecenia: prepare, report, serve."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


def _date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"niepoprawna data (oczekiwano RRRR-MM-DD): {s}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ztm-viz", description="Wizualizacja opóźnień ZTM z archiwum GPS.")
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("prepare", help="przygotuj zbiór SQLite z archiwum")
    pr.add_argument("--archive", type=Path, required=True, help="katalog archiwum (runs/, snapshots/)")
    pr.add_argument("--gtfs", type=Path, required=True, help="pomocniczy GTFS (ZIP)")
    pr.add_argument("--lines", nargs="+", required=True, metavar="LINIA", help="publiczne nazwy linii (routeShortName)")
    pr.add_argument("--out", type=Path, required=True, help="plik wynikowy SQLite")
    pr.add_argument("--from", dest="date_from", type=_date, help="pierwsza pełna doba (RRRR-MM-DD)")
    pr.add_argument("--to", dest="date_to", type=_date, help="ostatnia pełna doba (RRRR-MM-DD)")
    rp = sub.add_parser("report", help="wygeneruj statyczny raport HTML ze zbioru")
    rp.add_argument("--dataset", type=Path, required=True)
    rp.add_argument("--out", type=Path, required=True)
    sv = sub.add_parser("serve", help="lokalny podgląd raportu")
    sv.add_argument("--report", type=Path, required=True)
    sv.add_argument("--port", type=int, default=8000)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        from .pipeline import prepare
        prepare(args.archive, args.gtfs, args.out, list(dict.fromkeys(args.lines)), args.date_from, args.date_to)
    elif args.command == "report":
        from .export import report
        report(args.dataset, args.out)
    elif args.command == "serve":
        from .serve import serve
        serve(args.report, args.port)
    return 0


def entrypoint() -> None:
    sys.exit(main())
