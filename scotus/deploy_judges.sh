#!/usr/bin/env bash
# Run from repo root regardless of where this is invoked from.
cd "$(dirname "$0")/.." && python scotus/initialize_judges.py
