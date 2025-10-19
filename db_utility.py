#!/usr/bin/env python3
"""
Database utility script for managing DynamoDB tables.
Usage: python db_utility.py [command]
"""

import boto3
import sys
import urllib.request
from datetime import datetime

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Table names
QUERIES_TABLE = 'scotus_queries'
JOB_PROGRESS_TABLE = 'scotus_job_progress'

def delete_all_rows():
    """Delete all rows from all tables."""
    tables = [QUERIES_TABLE, JOB_PROGRESS_TABLE]
    
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


def get_public_ip():
    """Get the public IP address as seen by the server."""
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Error getting public IP: {e}")
        return None

def reset_my_ip(ip_address):
    """Modify IP address by appending '*' to reset query limit."""
    try:
        from boto3.dynamodb.conditions import Attr

        # Find queries with this IP address
        queries_table = dynamodb.Table(QUERIES_TABLE)
        queries_response = queries_table.scan(
            FilterExpression=Attr('ip_address').eq(ip_address)
        )
        queries_items = queries_response['Items']

        print(f"Found {len(queries_items)} queries for IP {ip_address}")

        # Modify IP address for each query
        modified_count = 0
        for item in queries_items:
            old_key = item['ipaddress_timestamp']

            # Create new item with modified IP
            new_item = item.copy()
            new_item['ip_address'] = ip_address + '*'

            # Update the key if it contains the IP address
            new_key = old_key.replace(ip_address, ip_address + '*')
            new_item['ipaddress_timestamp'] = new_key

            # Delete old item and create new one with modified IP
            with queries_table.batch_writer() as batch:
                batch.delete_item(Key={'ipaddress_timestamp': old_key})
                batch.put_item(Item=new_item)

            modified_count += 1

        print(f"Modified {modified_count} queries - IP changed to: {ip_address}*")
        print(f"\nSuccessfully reset query limit for IP: {ip_address}")

    except Exception as e:
        print(f"Error resetting IP: {e}")

def show_help():
    """Show usage help."""
    print("""
Database Utility Commands:
  delete-all          - Delete all rows from all tables
  queries             - Show all queries
  reset-ip [IP]       - Reset query limit for IP (auto-detects your public IP if not provided)
  help                - Show this help message

Examples:
  python db_utility.py delete-all
  python db_utility.py queries
  python db_utility.py reset-ip                  # Auto-detect your public IP
  python db_utility.py reset-ip 192.168.1.1      # Reset specific IP
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
    elif command == 'reset-ip':
        # Get IP address from argument or auto-detect
        if len(sys.argv) >= 3:
            ip_address = sys.argv[2]
            print(f"Resetting query limit for IP: {ip_address}")
        else:
            print("No IP address provided. Auto-detecting your public IP...")
            ip_address = get_public_ip()
            if not ip_address:
                print("Error: Could not auto-detect public IP address")
                print("Usage: python db_utility.py reset-ip <IP_ADDRESS>")
                return
            print(f"Detected public IP: {ip_address}")
            print(f"Resetting query limit for this IP...")
        reset_my_ip(ip_address)
    elif command == 'help':
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == '__main__':
    main()
