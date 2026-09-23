# Query History Buffer

## Description
A durable, high-performance analytical buffer for tracking and querying historical system interactions.

## Architecture Overview
Embedded DuckDB database leveraging columnar storage and vectorized execution for rapid historical aggregations.

### Database Engine Comparison
| Database Engine | Storage Orientation | Optimal Workload | Concurrency Model |
|---|---|---|---|
| **SQLite** | Row-oriented | High-frequency point inserts/updates | Multiple readers, single writer |
| **DuckDB** | Columnar | Large-scale aggregations, scans, analytics | Highly parallelized reads, single writer |

## Prerequisites
* Python 3.11+
* `duckdb`

## Environment Variables
* `DUCKDB_STORAGE_PATH`
* `MAX_HISTORY_RETENTION_DAYS`

## Quick Start & Usage
Connect to the DuckDB instance to execute complex SQL aggregations over the interaction history logs.

## Testing & CI
Validates the insertion of batch records and ensures that analytical queries process correctly without memory overflows.
