#!/usr/bin/env python3
"""
Database utility script for managing DynamoDB tables.
Usage: python db_utility.py [command]
"""

import boto3
import sys
from datetime import datetime

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Table names
QUERIES_TABLE = 'scotus_queries'
RESPONSES_TABLE = 'scotus_responses'
JOB_PROGRESS_TABLE = 'scotus_job_progress'

def delete_all_rows():
    """Delete all rows from all tables."""
    tables = [QUERIES_TABLE, RESPONSES_TABLE, JOB_PROGRESS_TABLE]
    
    for table_name in tables:
        try:
            table = dynamodb.Table(table_name)
            print(f"Deleting all rows from {table_name}...")
            
            # Scan and delete all items
            response = table.scan()
            items = response['Items']
            
            with table.batch_writer() as batch:
                for item in items:
                    # Get the key for deletion
                    if table_name == JOB_PROGRESS_TABLE:
                        key = {'job_id': item['job_id']}
                    else:
                        key = {'ipaddress_timestamp': item['ipaddress_timestamp']}
                    batch.delete_item(Key=key)
            
            print(f"Deleted {len(items)} items from {table_name}")
            
        except Exception as e:
            print(f"Error deleting from {table_name}: {e}")

def select_queries():
    """Select and display all queries."""
    try:
        table = dynamodb.Table(QUERIES_TABLE)
        response = table.scan()
        items = response['Items']
        
        print(f"\n=== QUERIES ({len(items)} total) ===")
        for item in items:
            timestamp = item.get('timestamp', 'N/A')
            ip = item.get('ip_address', 'N/A')
            question = item.get('question', 'N/A')
            print(f"[{timestamp}] {ip}: {question}")
            
    except Exception as e:
        print(f"Error reading queries: {e}")

def select_queries_and_responses():
    """Select and display queries with their responses."""
    try:
        # Get queries
        queries_table = dynamodb.Table(QUERIES_TABLE)
        queries_response = queries_table.scan()
        queries = {item['ipaddress_timestamp']: item for item in queries_response['Items']}
        
        # Get responses
        responses_table = dynamodb.Table(RESPONSES_TABLE)
        responses_response = responses_table.scan()
        responses = responses_response['Items']
        
        print(f"\n=== QUERIES & RESPONSES ({len(responses)} responses) ===")
        for response in responses:
            query_key = response.get('ipaddress_timestamp', '')
            query = queries.get(query_key, {})
            
            timestamp = query.get('timestamp', 'N/A')
            ip = query.get('ip_address', 'N/A')
            question = query.get('question', 'N/A')
            judge = response.get('judge_title', 'N/A')
            brief = response.get('brief_response', 'N/A')
            
            print(f"\n[{timestamp}] {ip}")
            print(f"Q: {question}")
            print(f"A ({judge}): {brief}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error reading queries and responses: {e}")

def show_help():
    """Show usage help."""
    print("""
Database Utility Commands:
  delete-all    - Delete all rows from all tables
  queries       - Show all queries
  full          - Show queries with responses
  help          - Show this help message
  
Examples:
  python db_utility.py delete-all
  python db_utility.py queries
  python db_utility.py full
""")

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'delete-all':
        confirm = input("Are you sure you want to delete ALL data? (yes/no): ")
        if confirm.lower() == 'yes':
            delete_all_rows()
        else:
            print("Operation cancelled.")
    elif command == 'queries':
        select_queries()
    elif command == 'full':
        select_queries_and_responses()
    elif command == 'help':
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == '__main__':
    main()
