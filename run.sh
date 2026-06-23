#!/bin/sh
# Launch the Quart ASGI app under the Lambda Web Adapter.
# uvicorn (single worker) avoids hypercorn's multiprocessing SemLock, which
# fails on Lambda (no /dev/shm named semaphores).
# --timeout-keep-alive 0: close the connection after each response. Lambda
# streaming leaves a kept-alive connection unusable, so the next request on a
# reused connection gets RST_STREAM (the "2nd query fails" bug). No reuse -> fix.
exec python -m uvicorn app:app --host 0.0.0.0 --port 8080 --timeout-keep-alive 0
