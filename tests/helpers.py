import json
import sqlite3

from ztm_viz.cli import main


def prepare(archive, gtfs, out, lines, *extra):
    argv = ["prepare", "--archive", str(archive), "--gtfs", str(gtfs), "--out", str(out), "--lines", *lines, *extra]
    return main(argv)


def rows(db, sql, *args):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def quality(out):
    return json.loads(out.with_suffix(".quality.json").read_text())
