#!/bin/sh
# Launch the Quart ASGI app under the Lambda Web Adapter.
# uvicorn (single worker) avoids hypercorn's multiprocessing SemLock, which
# fails on Lambda (no /dev/shm named semaphores).
exec python -m uvicorn app:app --host 0.0.0.0 --port 8080
