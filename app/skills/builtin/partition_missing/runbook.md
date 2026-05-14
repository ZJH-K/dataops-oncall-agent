# Partition Missing

## Goal

Diagnose why a table partition is missing, delayed, or not ready for a business date.

## Required Evidence

- Partition status for the target table and date.
- Related task run status for the producing DAG.
- Upstream table or partition status when available.
- Downstream tables that may consume the missing partition.

## Report Expectations

The report should distinguish between a missing partition, delayed production, failed production, and insufficient evidence.
