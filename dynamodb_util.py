"""
DynamoDB utility functions for production deployment.
"""

import boto3
from datetime import datetime
from typing import Dict, Any, Optional

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Table names
JOB_PROGRESS_TABLE = 'scotus_job_progress'
QUERIES_TABLE = 'scotus_queries'
RESPONSES_TABLE = 'scotus_responses'


def save_job_progress(job_id: str, progress_data: Dict[str, Any]) -> None:
    """Save job progress to DynamoDB."""
    try:
        table = dynamodb.Table(JOB_PROGRESS_TABLE)
        table.put_item(Item={
            'job_id': job_id,
            'timestamp': datetime.now().isoformat(),
            'status': progress_data.get('status', 'processing'),
            'total': progress_data.get('total', 0),
            'completed': progress_data.get('completed', 0),
            'responses': progress_data.get('responses', []),
            'question': progress_data.get('question', ''),
            'ttl': int(datetime.now().timestamp()) + 3600  # Expire after 1 hour
        })
    except Exception as e:
        print(f"Error saving job progress: {e}")


def get_job_progress(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job progress from DynamoDB."""
    try:
        table = dynamodb.Table(JOB_PROGRESS_TABLE)
        response = table.get_item(Key={'job_id': job_id})

        if 'Item' in response:
            item = response['Item']
            # Convert DynamoDB format back to app format
            return {
                'status': item.get('status', 'processing'),
                'total': item.get('total', 0),
                'completed': item.get('completed', 0),
                'responses': item.get('responses', []),
                'question': item.get('question', ''),
                'summary': _calculate_summary(item.get('responses', []))
            }
        return None
    except Exception as e:
        print(f"Error getting job progress: {e}")
        return None


def _calculate_summary(responses: list) -> Dict[str, list]:
    """Calculate summary from responses."""
    summary = {}
    for response in responses:
        level = response.get('support_level', 'neutral')
        if level not in summary:
            summary[level] = []
        summary[level].append(response.get('judge_title', ''))
    return summary


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

        # Query by partition key prefix
        response = table.query(
            KeyConditionExpression='begins_with(ipaddress_timestamp, :ip)',
            ExpressionAttributeValues={':ip': ip_address}
        )

        return response['Count']
    except Exception as e:
        print(f"Error getting IP query count: {e}")
        return 0
