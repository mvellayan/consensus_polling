#!/bin/sh
# Launch the Quart ASGI app under the Lambda Web Adapter.
# uvicorn (single worker) avoids hypercorn's multiprocessing SemLock, which
# fails on Lambda (no /dev/shm named semaphores).
# NB: do NOT set --timeout-keep-alive 0 — it closes the connection during the
# silent reasoning gap before the syllabus streams (9-judge runs), cancelling
# the response ("ASGI callable returned without completing response"). The
# connection-reuse reset is handled by the frontend retry instead.
exec python -m uvicorn app:app --host 0.0.0.0 --port 8080
