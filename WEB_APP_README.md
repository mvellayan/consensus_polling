# AI Supreme Court Web Application

A beautiful, modern web interface for querying AI-powered Supreme Court Justices.

## Features

### 🎨 Modern UI Design
- **Court Background**: Faded court/Lady Justice background image for an authentic legal atmosphere
- **Two-Column Layout**:
  - Left column: Justice selection panel with profile pictures
  - Right column: Question input and responses
- **Responsive Design**: Works seamlessly on desktop and mobile devices

### 👨‍⚖️ Justice Selection
- **Profile Pictures**: Each justice displayed with their official portrait
- **Toggleable Selection**: Click any justice to select/deselect
- **Select All Button**: Quickly select or deselect all justices at once
- Located in the left sidebar for easy access

### 💬 Question & Response Interface
- **Question Input**: Large text area for legal questions
- **Ask Button**: Positioned to the right of the question box
- **Loading State**:
  - Shows "Please wait. This could take 1+ minute"
  - Displays comprehensive disclaimer about educational use
- **Color-Coded Responses**: Each response has a colored border indicating the justice's stance:
  - 🟢 Green: Strongly Support / Support
  - ⚫ Gray: Neutral
  - 🟠 Orange: Oppose
  - 🔴 Red: Strongly Oppose
- **Expandable Details**: Click any response to see the full judicial opinion

### 📊 Features & Protections
- **Database Logging**: All questions, responses, and IP addresses are logged to SQLite
- **Rate Limiting**: 5 queries per IP address
- **Query Counter**: Footer displays "X of 5 questions remaining"
- **AI Sentiment Analysis**: Automatically determines each justice's support level

## Running the Application

```bash
# Start the web server
python app.py
```

The app will be available at: **http://localhost:5001**

## Files Structure

```
├── app.py                      # Flask backend server
├── templates/
│   └── index.html             # Main HTML template
├── static/
│   ├── style.css              # Styles with court background
│   ├── script.js              # Frontend JavaScript
│   └── court-background.jpg   # Background image
├── queries.db                 # SQLite database (created on first run)
├── judge_assistants.json      # Judge assistant configurations
└── judge_threads.json         # Judge thread IDs
```

## How It Works

1. **Select Justices**: Choose which justices to consult using the left sidebar
2. **Ask Question**: Enter your legal question in the text area
3. **Submit**: Click "Ask the AI Supreme Court"
4. **Wait**: The system queries each selected justice (can take 1+ minute)
5. **Review Responses**: Color-coded responses appear in the right column
6. **Expand Details**: Click any response to read the full opinion

## Database Schema

### `queries` table
- `id`: Query ID
- `ip_address`: User's IP address
- `question`: The question asked
- `timestamp`: When the query was made

### `responses` table
- `id`: Response ID
- `query_id`: Foreign key to queries table
- `judge_name`: Justice identifier (e.g., "roberts")
- `judge_title`: Justice's full title (e.g., "Justice Roberts")
- `response`: Full response text
- `support_level`: AI-analyzed sentiment (strongly_support, support, neutral, oppose, strongly_oppose)

## Legal Disclaimer

This AI simulation is for **educational and research use only** and does not represent real views or advice from any Justice or institution. All outputs are fictional and should not be relied upon for legal or factual purposes.

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Database**: SQLite
- **AI**: OpenAI Assistants API (GPT-4 for justices, GPT-4o-mini for sentiment analysis)
- **Images**: Wikipedia Commons (justice portraits)
