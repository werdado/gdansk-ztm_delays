# Working with the ZTM archive

This guide applies to the current fodler and its descendants. Paths below are relative to this directory. Preserve raw captures; write transformed data to a separate output location. This directory is ignored by Git.

## Locate files and their sources

```text
snapshots/<source>/<UTC-date>/<slot>/<attempt-id>.<format>.gz
runs/<UTC-date>/<slot>/<attempt-id>.json
gtfsgoogle.zip
docs/{gps.md,departures.md,gtfsgoogle.md,gtfs-realtime.proto}
```

| Source / file | Origin | Contents |
|---|---|---|
| `snapshots/gtfs-rt/` (`pb.gz`) | `https://ckan2.multimediagdansk.pl/gtfs-rt` | GTFS Realtime protobuf: trip updates and vehicle positions. |
| `snapshots/gps/` (`json.gz`) | `https://ckan2.multimediagdansk.pl/gpsPositions?v=2` | GPS JSON v2: vehicle positions, reported delays, GPS quality. |
| `snapshots/departures/` (`json.gz`) | `https://ckan2.multimediagdansk.pl/departures` | JSON keyed by stop pole: departure predictions and timetable fallback entries. |
| `runs/` (`json`) | Collector-generated | Acquisition manifests with source URLs, timing, outcomes, sizes, and snapshot keys. |
| `gtfsgoogle.zip` | Separate static ZTM GTFS dataset | Timetable tables; excluded from recurring collection. |
| `docs/` | Local format documentation and GTFS Realtime schema | Field descriptions and protobuf decoding definitions. |

`<slot>` is the intended UTC collection time, for example `2026-11-10T10:24:20.000Z`; `<UTC-date>` is its date. `<attempt-id>` is a UUID shared by one invocation's manifest and successful snapshots. Preserve separate attempts for the same slot.

The local archive paths mirror R2 object keys. The local download/sync procedure is undocumented. `.devcontainer/` and `.envrc` support the local environment and are outside the transport dataset.

## Trace provenance before analysis

1. Locate the manifest matching the snapshot's date, slot, and attempt ID. Match its `sources[]` entry by `key`; resolve that key relative to this directory. Record the entry's `url` and `status`. If either the manifest or snapshot is absent, record the gap.
2. Separate intended collection time (`scheduledFor`), actual acquisition times (`fetchedAt`, `receivedAt`, `storedAt`), and timestamps inside the payload. Use the timestamp appropriate to the analysis and identify it in the result.
3. Read the relevant format reference below before decoding fields or joining datasets. For joins, establish identifier compatibility and static timetable coverage from the selected files.
4. Report the files/time range inspected and unresolved provenance or coverage gaps. A sampled successful manifest supports claims about that capture only.

Run status is `complete`, `partial`, or `skipped`; source status is `stored` or `error`. Expired slots have `reason: slot_expired` and no source captures. Interruptions can leave snapshots without manifests. Treat missing observations as unknown. R2 custom metadata may retain provenance, but local downloads may omit it.

## Decode and interpret

The collector targets a capture approximately every 20 seconds, requesting all three feeds in parallel. Snapshots retain the original response bytes with lossless gzip, without filtering or deduplication. Decompress JSON with `gzip -dc <file.json.gz>`; decompress protobuf and decode it as `transit_realtime.FeedMessage`. Manifests are uncompressed JSON; static GTFS uses ZIP.

- **GPS analysis:** read [docs/gps.md](docs/gps.md) for fields, caching, freshness, and missing values. Reported delay and observed position are distinct measurements.
- **Departure analysis:** read [docs/departures.md](docs/departures.md) to distinguish realtime predictions from timetable fallback entries. Predictions do not establish actual departure times.
- **Protobuf decoding:** use [docs/gtfs-realtime.proto](docs/gtfs-realtime.proto). Its header identifies the upstream GTFS Specifications project; the exact copied revision is undocumented.
- **Timetable joins:** read [docs/gtfsgoogle.md](docs/gtfsgoogle.md) for table relationships and identifier conventions. Inspect the ZIP's calendar and feed metadata to establish coverage. Its exact download URL and acquisition time are undocumented; the intended catalog resource is recorded in [the project scope](../docs/ztm-poc-handoff.md). Documentation copy dates are also undocumented.
- **Collector behavior or completeness audits:** read [../README.md](../README.md), especially “Archive layout” and “Failure and timing behavior.” Confirm endpoint mapping, manifest fields, and key generation in [../src/index.ts](../src/index.ts). Continuous collection supersedes historical ten-day sizing assumptions in the research notes.
