"""Schemat SQLite zbioru pochodnego. Baza jest odtwarzalnym wynikiem przetwarzania."""
from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
create table meta(key text primary key, value text not null);
create table sources(
  id integer primary key, snapshot_key text, manifest_key text, run_status text, source_status text, url text,
  slot_utc integer not null, fetched_at text, received_at text, stored_at text,
  provenance_gap integer not null, read_error text, records integer not null default 0);
create table observations(
  id integer primary key, line text not null, vehicle_id integer not null, t_utc integer not null,
  route_id integer, trip_id integer, headsign text, vehicle_code text, vehicle_service text, sched_start integer,
  lat real, lon real, delay integer, speed real, direction integer, gps_quality integer,
  status text not null, conflict_reason text, raw_count integer not null,
  course_id integer, fragment_id integer, seq integer,
  s real, dist_line real, seg_id integer, phase text, flags text);
create index obs_course on observations(course_id, t_utc);
create table obs_sources(obs_id integer not null, source_id integer not null, primary key(obs_id, source_id));
create table courses(
  id integer primary key, line text not null, vehicle_service text not null, sched_start integer not null,
  dir integer, variant_key text, variant_status text, headsign text, vehicle_code text,
  t0 integer, t1 integer, n_obs integer, truncated text);
create table fragments(
  id integer primary key, course_id integer not null, vehicle_id integer, route_id integer, trip_id integer,
  t0 integer, t1 integer, n_obs integer, status text not null, match_fraction real, note text);
create table variants(
  line text not null, key text not null, route_id integer, trip_id integer, dir integer, headsign text,
  status text not null, note text, courses integer, observations integer, segments text,
  primary key(line, key));
create table segments(
  line text not null, id integer not null, dir integer, from_stop text, from_name text, from_lat real, from_lon real,
  to_stop text, to_name text, to_lat real, to_lon real, length_m real, path text, primary key(line, id));
create table segment_values(
  course_id integer not null, fragment_id integer not null, line text not null, seg_id integer not null,
  end_obs integer not null, end_t integer not null, end_delay integer not null, end_dist real, end_gap integer,
  start_obs integer, start_t integer, start_delay integer, start_kind text,
  primary key(course_id, seg_id));
create table segment_passes(
  course_id integer not null, fragment_id integer not null, line text not null, seg_id integer not null,
  has_value integer not null, has_change integer not null, note text, primary key(course_id, fragment_id, seg_id));
create table course_arrival(
  course_id integer primary key, obs_id integer, delay integer, uncertain text);
create table diagnostics(key text primary key, json text not null);
"""

OBS_COLUMNS = ("id", "line", "vehicle_id", "t_utc", "route_id", "trip_id", "headsign", "vehicle_code", "vehicle_service",
               "sched_start", "lat", "lon", "delay", "speed", "direction", "gps_quality", "status", "conflict_reason",
               "raw_count", "course_id", "fragment_id", "seq", "s", "dist_line", "seg_id", "phase", "flags")


def create(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("insert into meta values('schema_version', ?)", (str(SCHEMA_VERSION),))
    return con
