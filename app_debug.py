import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'env_check': bool(os.environ.get('OPENAI_API_KEY'))})

@app.route('/')
def index():
    return jsonify({'message': 'AI Supreme Court Debug Mode', 'openai_key_present': bool(os.environ.get('OPENAI_API_KEY'))})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
