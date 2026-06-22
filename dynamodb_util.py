"""
DynamoDB utility functions for production deployment.

Sync boto3 only — callers in the async app MUST wrap these in
asyncio.to_thread(...) so the event loop never blocks.
"""

import os
import boto3
from boto3.dynamodb.conditions import Attr
from datetime import datetime

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Table names (parameterized via env; no job_progress table anymore)
QUERIES_TABLE = os.environ.get("QUERIES_TABLE", "scotus_queries")
RESPONSES_TABLE = os.environ.get("RESPONSES_TABLE", "scotus_responses")


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

        return query_id
    except Exception as e:
        print(f"Error logging query: {e}")
        return f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"


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
    """Get the number of queries made by this IP address in DynamoDB."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        print(f"DEBUG: Searching for IP address: '{ip_address}'")

        # Use scan with filter instead of query
        response = table.scan(
            FilterExpression=Attr('ip_address').eq(ip_address)
        )

        print(f"DEBUG: Found {response['Count']} records for IP {ip_address}")
        if ip_address in ['127.0.0.1', 'localhost']:
            response['Count'] = 0  # exception for localhost.

        return response['Count']
    except Exception as e:
        print(f"Error getting IP query count: {e}")
        return 0


def get_total_query_count() -> int:
    """Get the total number of queries in DynamoDB."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        response = table.scan(Select='COUNT')
        return response.get('Count', 0)
    except Exception as e:
        print(f"Error getting total query count: {e}")
        return 0
