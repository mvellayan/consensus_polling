#!/bin/sh
exec hypercorn app:app -b 0.0.0.0:8080
