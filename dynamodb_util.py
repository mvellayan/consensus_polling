"""
DynamoDB utility functions for production deployment.

Sync boto3 only — callers in the async app MUST wrap these in
asyncio.to_thread(...) so the event loop never blocks.

Counting strategy (replaces the old full-table scans):
  - per-IP count  → Query the `ip_address-index` GSI (partition = ip_address)
  - global total  → an atomic counter item (PK `__total__`) bumped on each
                    log_query. Fresh tables start at 0, so the counter is exact.
                    The counter item carries no `ip_address` attribute, so it is
                    absent from the GSI and never pollutes the per-IP count.
"""

import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Table names (parameterized via env; no job_progress table anymore)
QUERIES_TABLE = os.environ.get("QUERIES_TABLE", "scotus_queries")
RESPONSES_TABLE = os.environ.get("RESPONSES_TABLE", "scotus_responses")

# GSI name must match the CDK stack (infra/scotus_stack.py).
IP_ADDRESS_INDEX = os.environ.get("IP_ADDRESS_INDEX", "ip_address-index")

# Reserved PK for the atomic global-total counter item.
TOTAL_COUNTER_KEY = "__total__"

_LOCALHOST = {"127.0.0.1", "localhost", "::1"}


def log_query(ip_address: str, question: str) -> str:
    """Log a query to DynamoDB and return a unique query ID."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        query_id = f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"

        table.put_item(Item={
            'ipaddress_timestamp': query_id,
            'ip_address': ip_address,
            'question': question,
            'timestamp': datetime.now().isoformat()
        })

        _increment_total_counter()
        return query_id
    except Exception as e:
        print(f"Error logging query: {e}")
        return f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"


def _increment_total_counter() -> None:
    """Atomically bump the global query counter. Best-effort — never raises."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        table.update_item(
            Key={'ipaddress_timestamp': TOTAL_COUNTER_KEY},
            UpdateExpression='ADD query_count :one',
            ExpressionAttributeValues={':one': 1},
        )
    except Exception as e:
        print(f"Error incrementing total counter: {e}")


def log_response(ip_address: str, query_id: str, judge_name: str, judge_title: str,
                 response: str, support_level: str) -> None:
    """Log a judge's response to DynamoDB."""
    try:
        table = dynamodb.Table(RESPONSES_TABLE)

        table.put_item(Item={
            'ipaddress_timestamp': f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}",
            'ip_address': ip_address,
            'query_id': query_id,
            'judge_name': judge_name,
            'judge_title': judge_title,
            'response': response,
            'support_level': support_level,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error logging response: {e}")


def get_ip_query_count(ip_address: str) -> int:
    """Count queries from this IP via the GSI (no full-table scan)."""
    if ip_address in _LOCALHOST:
        return 0
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        response = table.query(
            IndexName=IP_ADDRESS_INDEX,
            KeyConditionExpression=Key('ip_address').eq(ip_address),
            Select='COUNT',
        )
        return int(response.get('Count', 0))
    except Exception as e:
        print(f"Error getting IP query count: {e}")
        return 0


def get_total_query_count() -> int:
    """Read the atomic global counter (O(1), no scan)."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        resp = table.get_item(Key={'ipaddress_timestamp': TOTAL_COUNTER_KEY})
        item = resp.get('Item')
        if item and 'query_count' in item:
            return int(item['query_count'])
        return 0
    except Exception as e:
        print(f"Error getting total query count: {e}")
        return 0
