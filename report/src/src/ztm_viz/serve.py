"""Lokalny podgląd statycznego katalogu raportu (bez dodatkowych funkcji)."""
from __future__ import annotations

import functools
import http.server
from pathlib import Path


def serve(report: Path, port: int) -> None:
    report = Path(report)
    if not (report / "index.html").is_file():
        raise SystemExit(f"Niepoprawne wejście: {report} nie jest katalogiem raportu (brak index.html).")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(report))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        print(f"Raport: http://127.0.0.1:{port}/  (Ctrl+C kończy)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
