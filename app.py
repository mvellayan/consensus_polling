"""
Flask web server for AI Supreme Court application.
"""

import os
import json
import time
import sqlite3
import threading
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from typing import List, Dict
import boto3

dynamodb = boto3.resource('dynamodb')

# Progress tracking storage
job_progress = {}

# Progress tracking storage
job_progress = {}

try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Load .env from the same directory as this script
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not available in production

app = Flask(__name__)

# Initialize OpenAI client with error handling
try:
    client = OpenAI()
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None

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
    try:
        with open("judge_assistants.json", 'r') as f:
            assistants = json.load(f)
            return {a['judge_name']: a for a in assistants}
    except FileNotFoundError:
        print("ERROR: judge_assistants.json not found")
        return {}


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
    table = dynamodb.Table('scotus_queries')
    table.put_item(Item={
        'ipaddress_timestamp': f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}",
        'ip_address': ip_address,
        'question': question
    })
    return query_id


def log_response(ip_address: str, query_id: int, judge_name: str, judge_title: str, response: str, support_level: str):
    """Log a judge's response."""
    conn = sqlite3.connect('queries.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO responses (query_id, judge_name, judge_title, response, support_level)
        VALUES (?, ?, ?, ?, ?)
    ''', (query_id, judge_name, judge_title, response, support_level))
    conn.commit()
    conn.close()
    table = dynamodb.Table('scotus_responses')
    table.put_item(Item={
        'ipaddress_timestamp': f"{ip_address}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}",
        'ip_address': ip_address,
        'judge_name': judge_name,
        'judge_title': judge_title,
        'response': response,
        'support_level': support_level
    })



def analyze_support_level(response: str, question: str = "") -> str:
    """Analyze the response to determine support level based on Outcome field."""
    try:
        # Parse the first line to extract Outcome
        first_line = response.strip().split('\n')[0] if response else ""

        # Extract Outcome value
        outcome = 'neutral'
        if 'Outcome:' in first_line:
            # Extract text after "Outcome:" and before the next " - " or end of relevant section
            outcome_text = first_line.split('Outcome:')[1].strip()
            # Get just the outcome value (before " - Certainty" or similar)
            outcome_value = outcome_text.split(' - ')[0].strip().lower()

            # Map outcomes to support levels
            # Strike Down = strongly_oppose (striking down the law/action)
            # Uphold = strongly_support (upholding the law/action)
            # Remand = support (sending back, generally favorable)
            # Dismiss - Jurisdictional = neutral (no decision on merits)
            # Dismiss - Political Question = neutral (avoiding decision)

            if 'strike down' in outcome_value:
                outcome = 'strongly_oppose'
            elif 'uphold' in outcome_value:
                outcome = 'strongly_support'
            elif 'remand' in outcome_value:
                outcome = 'support'
            elif 'dismiss' in outcome_value:
                outcome = 'neutral'
            else:
                outcome = 'neutral'

        return outcome
    except Exception as e:
        print(f"Error analyzing support level: {e}")
        return 'neutral'


def query_judge(judge_name: str, vector_store_id: str, instructions: str, question: str, model: str = "gpt-5-nano") -> str:
    """Send a question to a specific judge and get their response using Responses API."""
    if not client:
        return "Error: OpenAI client not initialized"

    try:
        # Add length constraint to instructions
        enhanced_instructions = f"{instructions}\n\nIMPORTANT: Keep your response under 2000 characters. Be concise and focused."

        # Create a response with file search enabled
        response = client.responses.create(
            model=model,
            instructions=enhanced_instructions,
            input=question,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            reasoning={
                "effort": "medium"
            }
        )

        # Extract the text response
        return response.output_text

    except Exception as e:
        return f"Error querying judge: {str(e)}"


@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'judges_loaded': len(load_judge_assistants())})


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

    # For single judge, process immediately
    if len(judge_names) == 1:
        query_id = log_query(ip_address, question)
        judge_assistants = load_judge_assistants()
        responses = []

        judge_name = judge_names[0]
        if judge_name in judge_assistants:
            judge_info = judge_assistants[judge_name]
            try:
                response = query_judge(
                    judge_name=judge_name,
                    vector_store_id=judge_info['vector_store_id'],
                    instructions=judge_info['instructions'],
                    question=question
                )
                support_level = analyze_support_level(response, question)
                brief = response[:150] + '...' if len(response) > 150 else response
                log_response(ip_address, query_id, judge_name, judge_info['judge_title'], response, support_level)
                
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

    # For multiple judges, start async processing
    job_id = str(uuid.uuid4())
    job_progress[job_id] = {
        'status': 'processing',
        'total': len(judge_names),
        'completed': 0,
        'responses': [],
        'question': question
    }

    # Start background processing
    thread = threading.Thread(target=process_judges_async, args=(job_id, question, judge_names, ip_address))
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id})

@app.route('/api/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    """Get progress of a judge query job."""
    if job_id not in job_progress:
        return jsonify({'error': 'Job not found'}), 404
    
    progress_data = job_progress[job_id].copy()
    
    # Calculate summary for real-time display
    summary = {}
    for response in progress_data['responses']:
        level = response.get('support_level', 'neutral')
        if level not in summary:
            summary[level] = []
        summary[level].append(response['judge_title'])
    
    progress_data['summary'] = summary
    return jsonify(progress_data)

def process_judges_async(job_id, question, judge_names, ip_address):
    """Process judges asynchronously with progress updates."""
    query_id = log_query(ip_address, question)
    judge_assistants = load_judge_assistants()
    
    for i, judge_name in enumerate(judge_names):
        if judge_name not in judge_assistants:
            job_progress[job_id]['completed'] = i + 1
            continue

        judge_info = judge_assistants[judge_name]
        try:
            response = query_judge(
                judge_name=judge_name,
                vector_store_id=judge_info['vector_store_id'],
                instructions=judge_info['instructions'],
                question=question
            )
            support_level = analyze_support_level(response, question)
            brief = response[:150] + '...' if len(response) > 150 else response
            log_response(ip_address, query_id, judge_name, judge_info['judge_title'], response, support_level)
            
            job_progress[job_id]['responses'].append({
                'judge_name': judge_name,
                'judge_title': judge_info['judge_title'],
                'brief': brief,
                'full_response': response,
                'support_level': support_level
            })
        except Exception as e:
            job_progress[job_id]['responses'].append({
                'judge_name': judge_name,
                'judge_title': judge_info['judge_title'],
                'brief': f'Error: {str(e)}',
                'full_response': f'Error: {str(e)}',
                'support_level': 'neutral'
            })
        
        job_progress[job_id]['completed'] = i + 1
    
    job_progress[job_id]['status'] = 'completed'


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
