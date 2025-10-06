"""
Flask web server for AI Supreme Court application.
"""

import os
import json
import time
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from typing import List, Dict

app = Flask(__name__)
client = OpenAI()

# Database initialization
def init_db():
    """Initialize SQLite database for logging."""
    conn = sqlite3.connect('queries.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            question TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER NOT NULL,
            judge_name TEXT NOT NULL,
            judge_title TEXT NOT NULL,
            response TEXT NOT NULL,
            support_level TEXT,
            FOREIGN KEY (query_id) REFERENCES queries(id)
        )
    ''')
    conn.commit()
    conn.close()

# if queries.db file does not exist, call init_db
if not os.path.exists('queries.db'):
    init_db()



def load_judge_assistants() -> Dict[str, Dict]:
    """Load judge assistant information from the saved JSON file."""
    with open("judge_assistants.json", 'r') as f:
        assistants = json.load(f)
        return {a['judge_name']: a for a in assistants}


def get_ip_query_count(ip_address: str) -> int:
    """Get the number of queries made by this IP address."""
    conn = sqlite3.connect('queries.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM queries WHERE ip_address = ?', (ip_address,))
    count = c.fetchone()[0]
    conn.close()
    return count


def log_query(ip_address: str, question: str) -> int:
    """Log a query and return the query ID."""
    conn = sqlite3.connect('queries.db')
    c = conn.cursor()
    c.execute('INSERT INTO queries (ip_address, question) VALUES (?, ?)', (ip_address, question))
    query_id = c.lastrowid
    conn.commit()
    conn.close()
    return query_id


def log_response(query_id: int, judge_name: str, judge_title: str, response: str, support_level: str):
    """Log a judge's response."""
    conn = sqlite3.connect('queries.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO responses (query_id, judge_name, judge_title, response, support_level)
        VALUES (?, ?, ?, ?, ?)
    ''', (query_id, judge_name, judge_title, response, support_level))
    conn.commit()
    conn.close()


def analyze_support_level(response: str) -> str:
    """Analyze the response to determine support level using OpenAI."""
    try:
        analysis = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are analyzing a Supreme Court Justice's response. Determine if they are 'strongly_support', 'support', 'neutral', 'oppose', or 'strongly_oppose' based on the tone and content. Respond with ONLY one of these five words."},
                {"role": "user", "content": response}
            ],
            temperature=0.3,
            max_tokens=10
        )
        level = analysis.choices[0].message.content.strip().lower()
        if level in ['strongly_support', 'support', 'neutral', 'oppose', 'strongly_oppose']:
            return level
        return 'neutral'
    except:
        return 'neutral'


def query_judge(judge_name: str, assistant_id: str, thread_id: str, question: str) -> str:
    """Send a question to a specific judge and get their response."""
    # Add the user's question to the thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=question
    )

    # Create a run with the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    # Wait for the run to complete
    while run.status in ['queued', 'in_progress', 'requires_action']:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

    if run.status == 'completed':
        # Get the assistant's messages
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order='desc',
            limit=1
        )

        # Extract the response
        if messages.data:
            response_message = messages.data[0]
            if response_message.content:
                text_parts = []
                for content in response_message.content:
                    if hasattr(content, 'text'):
                        text_parts.append(content.text.value)
                return '\n'.join(text_parts)

    return f"Error: Run status was {run.status}"


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/judges')
def get_judges():
    """Get list of all judges."""
    judge_assistants = load_judge_assistants()

    # Judge profile pictures
    judge_images = {
        'alito': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Associate_Justice_Samuel_A._Alito%2C_Jr._%28cropped%29.jpg/220px-Associate_Justice_Samuel_A._Alito%2C_Jr._%28cropped%29.jpg',
        'barrett': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Associate_Justice_Amy_Coney_Barrett_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Amy_Coney_Barrett_Official_Portrait_%28cropped%29.jpg',
        'gorsuch': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Associate_Justice_Neil_Gorsuch_Official_Portrait_%28cropped_2%29.jpg/220px-Associate_Justice_Neil_Gorsuch_Official_Portrait_%28cropped_2%29.jpg',
        'jackson': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Ketanji_Brown_Jackson_official_SCOTUS_portrait_%28cropped%29.jpg/220px-Ketanji_Brown_Jackson_official_SCOTUS_portrait_%28cropped%29.jpg',
        'kagan': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Associate_Justice_Elena_Kagan_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Elena_Kagan_Official_Portrait_%28cropped%29.jpg',
        'kavanaugh': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Associate_Justice_Brett_Kavanaugh_Official_Portrait_%28cropped%29.jpg/220px-Associate_Justice_Brett_Kavanaugh_Official_Portrait_%28cropped%29.jpg',
        'roberts': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Chief_Justice_John_G._Roberts%2C_Jr._%28Cropped%29.jpg/220px-Chief_Justice_John_G._Roberts%2C_Jr._%28Cropped%29.jpg',
        'sotomayor': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Sonia_Sotomayor_in_SCOTUS_robe_crop.jpg/220px-Sonia_Sotomayor_in_SCOTUS_robe_crop.jpg',
        'thomas': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Associate_Justice_Clarence_Thomas%2C_official_SCOTUS_portrait%2C_crop.jpg/220px-Associate_Justice_Clarence_Thomas%2C_official_SCOTUS_portrait%2C_crop.jpg'
    }

    judges = [
        {
            'judge_name': name,
            'judge_title': info['judge_title'],
            'image': judge_images.get(name, 'https://via.placeholder.com/48')
        }
        for name, info in judge_assistants.items()
    ]
    return jsonify(judges)


@app.route('/api/check-limit')
def check_limit():
    """Check if IP has reached query limit."""
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    count = get_ip_query_count(ip_address)
    return jsonify({
        'count': count,
        'remaining': max(0, 5 - count),
        'limit_reached': count >= 5
    })


@app.route('/api/query', methods=['POST'])
def query_judges():
    """Query selected judges with a question."""
    data = request.json
    question = data.get('question', '').strip()
    judge_names = data.get('judges', [])

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    if not judge_names:
        return jsonify({'error': 'At least one judge must be selected'}), 400

    # Check IP rate limit
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if get_ip_query_count(ip_address) >= 5:
        return jsonify({'error': 'Query limit reached. Maximum 5 queries per IP address.'}), 429

    # Log the query
    query_id = log_query(ip_address, question)

    # Query judges
    judge_assistants = load_judge_assistants()
    responses = []

    for judge_name in judge_names:
        if judge_name not in judge_assistants:
            continue

        judge_info = judge_assistants[judge_name]

        try:
            response = query_judge(
                judge_name=judge_name,
                assistant_id=judge_info['assistant_id'],
                thread_id=judge_info['thread_id'],
                question=question
            )

            # Analyze support level
            support_level = analyze_support_level(response)

            # Create brief summary (first 150 chars)
            brief = response[:150] + '...' if len(response) > 150 else response

            # Log the response
            log_response(query_id, judge_name, judge_info['judge_title'], response, support_level)

            responses.append({
                'judge_name': judge_name,
                'judge_title': judge_info['judge_title'],
                'brief': brief,
                'full_response': response,
                'support_level': support_level
            })

        except Exception as e:
            responses.append({
                'judge_name': judge_name,
                'judge_title': judge_info['judge_title'],
                'brief': f'Error: {str(e)}',
                'full_response': f'Error: {str(e)}',
                'support_level': 'neutral'
            })

    return jsonify({
        'question': question,
        'responses': responses
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
