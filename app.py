"""
Quart (async) web server for the AI Supreme Court application.

Full token streaming for all selected judges, multiplexed into one
newline-delimited JSON response stream. No daemon threads, no
ThreadPoolExecutor, no job_progress polling.
"""

import os
import re
import json
import asyncio
from typing import Dict, List, Optional

from quart import Quart, render_template, request, jsonify, Response
from openai import AsyncOpenAI

import dynamodb_util

try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Load .env from the same directory as this script
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not available in production

app = Quart(__name__)

MODEL = "gpt-5-nano"
QUERY_PREFIX = (
    "Can you decide if this is constitutional, follows federal laws, "
    "and respects power balance and individual rights? "
)

# Judge profile pictures
JUDGE_IMAGES = {
    'alito': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Associate_Justice_Samuel_A._Alito%2C_Jr._%28cropped%29.jpg/220px-Associate_Justice_Samuel_A._Alito%2C_Jr._%28cropped%29.jpg',
    'barrett': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Associate_Justice_Amy_Coney_Barrett_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Amy_Coney_Barrett_Official_Portrait_%28cropped%29.jpg',
    'gorsuch': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Associate_Justice_Neil_Gorsuch_Official_Portrait_%28cropped_2%29.jpg/220px-Associate_Justice_Neil_Gorsuch_Official_Portrait_%28cropped_2%29.jpg',
    'jackson': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Ketanji_Brown_Jackson_official_SCOTUS_portrait_%28cropped%29.jpg/220px-Ketanji_Brown_Jackson_official_SCOTUS_portrait_%28cropped%29.jpg',
    'kagan': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Associate_Justice_Elena_Kagan_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Elena_Kagan_Official_Portrait_%28cropped%29.jpg',
    'kavanaugh': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Associate_Justice_Brett_Kavanaugh_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Brett_Kavanaugh_Official_Portrait_%28cropped%29.jpg',
    'roberts': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Chief_Justice_John_G._Roberts%2C_Jr._%28Cropped%29.jpg/220px-Chief_Justice_John_G._Roberts%2C_Jr._%28Cropped%29.jpg',
    'sotomayor': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Sonia_Sotomayor_in_SCOTUS_robe_crop.jpg/220px-Sonia_Sotomayor_in_SCOTUS_robe_crop.jpg',
    'thomas': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Associate_Justice_Clarence_Thomas%2C_official_SCOTUS_portrait%2C_crop.jpg/220px-Associate_Justice_Clarence_Thomas%2C_official_SCOTUS_portrait%2C_crop.jpg',
}

# In Lambda the OpenAI key lives in SSM (OPENAI_API_KEY_PARAM); locally it comes
# from .env. Fetch + export it before constructing the client.
if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_API_KEY_PARAM"):
    try:
        import boto3
        _val = boto3.client("ssm").get_parameter(
            Name=os.environ["OPENAI_API_KEY_PARAM"], WithDecryption=True
        )["Parameter"]["Value"]
        os.environ["OPENAI_API_KEY"] = _val
        print("Loaded OPENAI_API_KEY from SSM")
    except Exception as e:
        print(f"Error loading OPENAI_API_KEY from SSM: {e}")

# Initialize the async OpenAI client with error handling
try:
    client = AsyncOpenAI()
    print("OpenAI async client initialized successfully")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None


def load_judge_assistants() -> Dict[str, Dict]:
    """Load judge assistant information from the saved JSON file."""
    try:
        with open("scotus/judge_assistants.json", 'r') as f:
            assistants = json.load(f)
            return {a['judge_name']: a for a in assistants}
    except FileNotFoundError:
        print("ERROR: judge_assistants.json not found")
        return {}


def analyze_support_level(response: str, question: str = "") -> str:
    """Analyze the response to extract the Outcome disposition (line 1)."""
    try:
        first_line = response.strip().split('\n')[0] if response else ""
        first_line_lower = first_line.lower()

        valid_outcomes = ['support', 'overturn', 'remand']
        for valid_outcome in valid_outcomes:
            if valid_outcome in first_line_lower:
                return valid_outcome

        return 'unknown'
    except Exception as e:
        print(f"Error analyzing outcome: {e}")
        return 'unknown'


def parse_certainty_scope(response: str) -> Dict[str, Optional[str]]:
    """Parse line 2 for the Certainty and Scope axes.

    Line 2 format:  Certainty: [Definitive|Likely|Qualified|Conditional]
                    and Scope: [Broad|Narrow|Facial|As-Applied]

    Defensive like analyze_support_level: missing -> None, never raises.
    """
    result: Dict[str, Optional[str]] = {"certainty": None, "scope": None}
    _CERTAINTY = ('Definitive', 'Likely', 'Qualified', 'Conditional')
    _SCOPE = {'broad': 'Broad', 'narrow': 'Narrow',
              'facial': 'Facial', 'as-applied': 'As-Applied'}
    try:
        lines = response.strip().split('\n') if response else []
        if len(lines) < 2:
            return result
        second_line = lines[1]

        # Models drift on the labels (e.g. "Certainty: Definitive | Facial" drops
        # the "Scope:" label). Prefer the labeled form, then fall back to a bare
        # enum value on line 2 — the certainty/scope value sets are disjoint, so
        # matching the value itself is unambiguous.
        cert_alts = '|'.join(_CERTAINTY)
        certainty_match = (
            re.search(rf'Certainty:\s*\[?\s*({cert_alts})', second_line, re.IGNORECASE)
            or re.search(rf'\b({cert_alts})\b', second_line, re.IGNORECASE)
        )
        if certainty_match:
            result["certainty"] = certainty_match.group(1).capitalize()

        scope_alts = 'Broad|Narrow|Facial|As-Applied'
        scope_match = (
            re.search(rf'Scope:\s*\[?\s*({scope_alts})', second_line, re.IGNORECASE)
            or re.search(rf'\b({scope_alts})\b', second_line, re.IGNORECASE)
        )
        if scope_match:
            result["scope"] = _SCOPE.get(scope_match.group(1).lower(), scope_match.group(1))

        return result
    except Exception as e:
        print(f"Error parsing certainty/scope: {e}")
        return result


def calculate_summary(responses: List[Dict]) -> Dict[str, list]:
    """Group judge_title by outcome (support_level). REGRESSION-critical."""
    summary: Dict[str, list] = {}
    for response in responses:
        outcome = response.get('support_level', 'unknown')
        if outcome not in summary:
            summary[outcome] = []
        summary[outcome].append(response.get('judge_title', ''))
    return summary


def get_client_ip(req) -> str:
    """Real viewer IP behind CloudFront.

    CloudFront-Viewer-Address is CloudFront's own measurement of the TCP peer
    (the viewer) — the most authoritative source and not viewer-spoofable.
    Format: "1.2.3.4:port" (IPv4) or "[2600:..]:port" (IPv6). Fall back to the
    leftmost X-Forwarded-For, then remote_addr.
    """
    cf = req.headers.get('CloudFront-Viewer-Address')
    if cf:
        return cf.rsplit(':', 1)[0].strip('[]') or cf

    xff = req.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()

    return req.remote_addr or '127.0.0.1'


# --------------------------------------------------------------------------
# Simple (non-streaming) endpoints
# --------------------------------------------------------------------------

@app.route('/health')
async def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'judges_loaded': len(load_judge_assistants())})


@app.route('/')
async def index():
    """Serve the main page."""
    return await render_template('index.html')


@app.route('/api/judges')
async def get_judges():
    """Get list of all judges."""
    judge_assistants = load_judge_assistants()
    judges = [
        {
            'judge_name': name,
            'judge_title': info['judge_title'],
            'image': JUDGE_IMAGES.get(name, 'https://via.placeholder.com/48'),
        }
        for name, info in judge_assistants.items()
    ]
    return jsonify(judges)


@app.route('/api/check-limit')
async def check_limit():
    """Return this IP's address and how many queries it has made (no limit)."""
    ip_address = get_client_ip(request)
    count = await asyncio.to_thread(dynamodb_util.get_ip_query_count, ip_address)
    return jsonify({
        'ip_address': ip_address,
        'count': count,
    })


@app.route('/api/total-queries')
async def get_total_queries():
    """Get total query count (1200 + database count)."""
    db_count = await asyncio.to_thread(dynamodb_util.get_total_query_count)
    total = 1200 + db_count
    return jsonify({'total': total, 'db_count': db_count})


# --------------------------------------------------------------------------
# Streaming query endpoint
# --------------------------------------------------------------------------

# Sentinel used by the multiplexer to know a judge task has finished.
_DONE = object()


async def _stream_judge(judge_name: str, judge_info: Dict, question: str,
                        out_queue: "asyncio.Queue") -> Dict:
    """Stream one judge's tokens onto out_queue; return its completion dict.

    Tokens are pushed as ("token", {...}). On error a ("judge_error", {...})
    is pushed and an error dict is returned. Always pushes ("__done__", name)
    last so the multiplexer can track completion.
    """
    full_text_parts: List[str] = []
    judge_title = judge_info.get('judge_title', judge_name.title())
    try:
        if client is None:
            raise RuntimeError("OpenAI client not initialized")

        enhanced_instructions = (
            f"{judge_info['instructions']}\n\n"
            "OUTCOME DEFINITION (critical): the FIRST line must be exactly one of "
            "Support, Overturn, or Remand, judged about THE GOVERNMENT ACTION OR "
            "PROPOSITION IN THE QUESTION:\n"
            "  - Support  = it is CONSTITUTIONAL / the government MAY do it / upheld.\n"
            "  - Overturn = it is UNCONSTITUTIONAL / the government MAY NOT do it / struck down.\n"
            "  - Remand   = unclear, fact-dependent, or needs further proceedings.\n"
            "Your first-line label MUST match your reasoning. If you conclude the "
            "action is unconstitutional or not permitted, the first line MUST be "
            "'Overturn' (never 'Support').\n\n"
            "IMPORTANT: Keep your response under 2000 characters. "
            "Be concise and focused."
        )

        stream = await client.responses.create(
            model=MODEL,
            instructions=enhanced_instructions,
            input=question,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [judge_info['vector_store_id']],
            }],
            reasoning={"effort": "medium"},
            stream=True,
        )

        async for event in stream:
            etype = getattr(event, "type", None)
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    full_text_parts.append(delta)
                    await out_queue.put(("token", {
                        "type": "token",
                        "judge": judge_name,
                        "text": delta,
                    }))

        full_response = "".join(full_text_parts)
        outcome = analyze_support_level(full_response, question)
        axes = parse_certainty_scope(full_response)
        brief = full_response[:150] + '...' if len(full_response) > 150 else full_response

        result = {
            "judge_name": judge_name,
            "judge_title": judge_title,
            "full_response": full_response,
            "support_level": outcome,
            "brief": brief,
            "certainty": axes["certainty"],
            "scope": axes["scope"],
        }
        await out_queue.put(("judge_done", {
            "type": "judge_done",
            "judge": judge_name,
            "outcome": outcome,
            "certainty": axes["certainty"],
            "scope": axes["scope"],
            "full_response": full_response,
            "brief": brief,
        }))
        return result
    except Exception as e:
        error_msg = str(e)
        print(f"Error streaming judge {judge_name}: {error_msg}")
        await out_queue.put(("judge_error", {
            "type": "judge_error",
            "judge": judge_name,
            "error": error_msg,
        }))
        return {
            "judge_name": judge_name,
            "judge_title": judge_title,
            "full_response": f"Error: {error_msg}",
            "support_level": "unknown",
            "brief": f"Error: {error_msg}",
            "certainty": None,
            "scope": None,
            "error": error_msg,
        }
    finally:
        await out_queue.put(("__done__", judge_name))


def _build_tally_string(summary: Dict[str, list]) -> str:
    """Render the code-computed tally into a fixed, human-readable fact block."""
    parts = []
    for outcome in ("support", "overturn", "remand"):
        names = summary.get(outcome, [])
        if names:
            parts.append(f"{outcome.upper()} ({len(names)}): {', '.join(names)}")
    other = {k: v for k, v in summary.items()
             if k not in ("support", "overturn", "remand") and v}
    for outcome, names in other.items():
        parts.append(f"{outcome.upper()} ({len(names)}): {', '.join(names)}")
    return "\n".join(parts) if parts else "No outcomes recorded."


async def _stream_syllabus(completed: List[Dict], tally_string: str,
                           out_queue: "asyncio.Queue") -> Optional[str]:
    """Stream a grounded syllabus (N>=2) or a TL;DR (N==1)."""
    try:
        if client is None:
            raise RuntimeError("OpenAI client not initialized")

        answers_block = "\n\n".join(
            f"{c['judge_title']} ({c.get('support_level', 'unknown')}):\n{c['full_response']}"
            for c in completed
        )

        if len(completed) == 1:
            instructions = (
                "Translate this single Supreme Court opinion into 2-3 plain-English "
                "sentences a non-lawyer can understand. Do not add legal jargon."
            )
            prompt = answers_block
        else:
            instructions = (
                "You are writing a neutral syllabus summarizing how a panel of "
                "Supreme Court justices ruled.\n"
                "The vote count and which justice voted which way are GIVEN below "
                "and are CORRECT and FIXED. Explain the reasoning and the divide; "
                "never restate, recount, or change the vote count.\n\n"
                f"VOTE TALLY (GIVEN, CORRECT, DO NOT CHANGE):\n{tally_string}"
            )
            prompt = (
                "Here are the full opinions. Write a concise plain-English syllabus "
                "of the reasoning behind the ruling:\n\n" + answers_block
            )

        stream = await client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=prompt,
            reasoning={"effort": "medium"},
            stream=True,
        )

        parts: List[str] = []
        async for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    parts.append(delta)
                    await out_queue.put(("syllabus_token", {
                        "type": "syllabus_token",
                        "text": delta,
                    }))
        return "".join(parts)
    except Exception as e:
        error_msg = str(e)
        print(f"Error streaming syllabus: {error_msg}")
        await out_queue.put(("syllabus_error", {
            "type": "syllabus_error",
            "error": error_msg,
        }))
        return None
    finally:
        # Always signal completion so the drain loop terminates deterministically
        # (mirrors the per-judge __done__ sentinel — no timeout polling).
        await out_queue.put(("__syllabus_done__", {"type": "__syllabus_done__"}))


@app.route('/api/query', methods=['POST'])
async def query_judges():
    """Stream all selected judges' tokens + tally + syllabus as NDJSON."""
    data = await request.get_json()
    data = data or {}
    question = (data.get('question') or '').strip()
    judge_names = data.get('judges', [])

    if not question:
        return jsonify({'error': 'Question is required'}), 400
    if not judge_names:
        return jsonify({'error': 'At least one judge must be selected'}), 400

    question = QUERY_PREFIX + question

    # No query limit. IP is captured only for logging + the count display.
    ip_address = get_client_ip(request)

    judge_assistants = load_judge_assistants()
    selected = [(n, judge_assistants[n]) for n in judge_names if n in judge_assistants]

    if not selected:
        return jsonify({'error': 'No valid judges selected'}), 400

    async def event_stream():
        out_queue: "asyncio.Queue" = asyncio.Queue()
        completed: List[Dict] = []

        # Fan out one streaming task per selected judge.
        tasks = [
            asyncio.create_task(_stream_judge(name, info, question, out_queue))
            for name, info in selected
        ]
        remaining = len(tasks)

        try:
            # Multiplex judge tokens/events until every judge task signals done.
            while remaining > 0:
                kind, payload = await out_queue.get()
                if kind == "__done__":
                    remaining -= 1
                    continue
                yield (json.dumps(payload) + "\n").encode("utf-8")

            # All judge tasks finished; gather their results.
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    completed.append(r)

            # Tally computed IN CODE.
            summary = calculate_summary(completed)
            grouped = {
                "support": summary.get("support", []),
                "overturn": summary.get("overturn", []),
                "remand": summary.get("remand", []),
            }
            yield (json.dumps({"type": "tally", "summary": grouped}) + "\n").encode("utf-8")

            # Grounded syllabus stream (additive — errors don't abort).
            tally_string = _build_tally_string(summary)
            syllabus_task = asyncio.create_task(
                _stream_syllabus(completed, tally_string, out_queue)
            )
            # Drain syllabus tokens until the sentinel — deterministic, no polling.
            while True:
                kind, payload = await out_queue.get()
                if kind == "__syllabus_done__":
                    break
                yield (json.dumps(payload) + "\n").encode("utf-8")
            await syllabus_task
        finally:
            # Durable write even on client disconnect.
            try:
                query_id = await asyncio.to_thread(
                    dynamodb_util.log_query, ip_address, question
                )
                for c in completed:
                    await asyncio.to_thread(
                        dynamodb_util.log_response,
                        ip_address,
                        query_id,
                        c.get("judge_name", ""),
                        c.get("judge_title", ""),
                        c.get("full_response", ""),
                        c.get("support_level", "unknown"),
                    )
            except Exception as e:
                print(f"Error during durable write: {e}")
            # Make sure no judge task is left dangling.
            for t in tasks:
                if not t.done():
                    t.cancel()
            yield (json.dumps({"type": "done"}) + "\n").encode("utf-8")

    return Response(event_stream(), content_type="text/plain; charset=utf-8")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
