#!/usr/bin/env python3
import sqlite3
import argparse

def query_db():
    conn = sqlite3.connect('queries.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM queries ORDER BY ip_address, id')
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

def extend_ip(ip_address):
    conn = sqlite3.connect('queries.db')
    cursor = conn.cursor()
    new_ip = f"{ip_address}-1"
    cursor.execute('UPDATE queries SET ip_address = ? WHERE ip_address = ?', (new_ip, ip_address))
    conn.commit()
    print(f"Updated {cursor.rowcount} row(s): {ip_address} -> {new_ip}")
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-query', action='store_true', help='Query all records ordered by ip_address, id')
    parser.add_argument('-extend_ip', type=str, help='Extend IP address with -1 suffix')
    
    args = parser.parse_args()
    
    if args.query:
        query_db()
    elif args.extend_ip:
        extend_ip(args.extend_ip)
    else:
        parser.print_help()
