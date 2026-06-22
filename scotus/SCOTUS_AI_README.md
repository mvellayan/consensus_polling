# Supreme Court Judge AI Consensus Polling

This project creates AI agents representing the 9 current Supreme Court justices, allowing you to query them on legal questions based on their judicial philosophy and written opinions.

## Overview

The system consists of two main applications:

1. **`initialize_judges.py`** - Creates persistent OpenAI conversation threads for each of the 9 Supreme Court justices
2. **`query_judges.py`** - Sends questions to specified judges and collects their responses

Each judge agent is initialized with:
- All their written opinions from cases in the `scotus/` directory
- Case syllabi for context on the legal issues
- A system prompt that instructs them to respond from their judicial perspective

## Setup

### 1. Install Dependencies

```bash
pip install openai
```

### 2. Set OpenAI API Key

```bash
export OPENAI_API_KEY='your-api-key-here'
```

Or create a `.env` file with:
```
OPENAI_API_KEY=your-api-key-here
```

### 3. Ensure SCOTUS Data

Make sure you have JSON files in the `scotus/` directory with the naming format:
- `{case_number}_{judge_name}_{response_type}.json` - Individual judge opinions
- `{case_number}_syllabus.json` - Case summaries

## Usage

### Initialize Judge Agents

First, initialize the 9 judge conversation threads:

```bash
python initialize_judges.py
```

This will:
- Load all opinions and case data for each judge
- Create OpenAI conversation threads
- Save thread IDs to `judge_threads.json`

Example output:
```
============================================================
Initializing Supreme Court Judge AI Agents
============================================================

Initializing alito...
  - Loaded 15 opinions
  - Loaded 12 case syllabi
  ✓ Successfully initialized Justice Alito

...

Thread information saved to: judge_threads.json
Total judges initialized: 9/9
```

### Query Judges

#### Query specific judges:

```bash
python query_judges.py -j roberts kagan sotomayor -q "What is your view on stare decisis?"
```

#### Query all judges:

```bash
python query_judges.py --all -q "How should courts interpret the Commerce Clause?"
```

#### List available judges:

```bash
python query_judges.py --list
```

#### Save responses to a specific file:

```bash
python query_judges.py -j thomas alito -q "Discuss your approach to originalism" -o responses.json
```

## The 9 Justices

The system includes all current Supreme Court justices:

- **Justice Alito** (alito)
- **Justice Barrett** (barrett)
- **Justice Gorsuch** (gorsuch)
- **Justice Jackson** (jackson)
- **Justice Kagan** (kagan)
- **Justice Kavanaugh** (kavanaugh)
- **Chief Justice Roberts** (roberts)
- **Justice Sotomayor** (sotomayor)
- **Justice Thomas** (thomas)

## Data Format

### Opinion Files (`scotus/{case_number}_{judge_name}_{response_type}.json`)

```json
{
  "case_number": "22-1008",
  "judge": "barrett",
  "opinion_type": "opinion",
  "text": "SUPREME COURT OF THE UNITED STATES..."
}
```

### Syllabus Files (`scotus/{case_number}_syllabus.json`)

```json
{
  "syllabus": "Syllabus\n\nSUPREME COURT OF THE UNITED STATES..."
}
```

## Output Format

Query responses are saved as JSON:

```json
{
  "question": "What is your view on stare decisis?",
  "timestamp": "2024-10-05 14:30:00",
  "responses": {
    "roberts": "Response from Chief Justice Roberts...",
    "kagan": "Response from Justice Kagan...",
    "sotomayor": "Response from Justice Sotomayor..."
  }
}
```

## How It Works

### Initialization Process

1. For each judge, the system:
   - Scans the `scotus/` directory for all opinion files matching the judge's name
   - Loads the corresponding case syllabi
   - Creates a comprehensive system prompt including:
     - The judge's identity
     - Their written opinions (truncated to fit token limits)
     - Relevant case context
     - Instructions to respond from their judicial perspective
   - Creates an OpenAI thread with this context

2. Thread IDs are saved to `judge_threads.json` for later querying

### Query Process

1. Loads judge thread information from `judge_threads.json`
2. For each specified judge:
   - Sends the question to their conversation thread
   - Uses OpenAI's `gpt-4o-mini` model to generate a response
   - Collects and displays the response
3. Saves all responses to a timestamped JSON file

## Configuration

### Change the AI Model

Edit `query_judges.py` and modify the `MODEL` variable:

```python
MODEL = "gpt-4o-mini"  # or "gpt-4", "gpt-4-turbo", etc.
```

### Adjust Context Window

In `initialize_judges.py`, adjust truncation limits in `create_judge_system_prompt()`:

```python
# Currently set to:
syllabus_text = syllabus['syllabus'][:2000]  # First 2000 chars
opinion_text = opinion['text'][:3000]        # First 3000 chars
```

## Limitations

- **Token Limits**: Due to OpenAI token limits, opinions and syllabi are truncated. This means the AI may not have access to complete opinions.
- **Cost**: Each query costs OpenAI API credits. Be mindful when querying all 9 judges repeatedly.
- **Accuracy**: AI responses are based on patterns in the training data and provided context. They may not perfectly reflect actual judicial reasoning.
- **Recency**: The AI only knows about cases included in your `scotus/` directory.

## API Costs

Using `gpt-4o-mini` (recommended):
- Initialization: ~$0.50-1.00 for all 9 judges
- Each query per judge: ~$0.01-0.05

Using `gpt-4`:
- Significantly more expensive (10-30x)

## Troubleshooting

### "judge_threads.json not found"

Run `initialize_judges.py` first to create the judge threads.

### "Judge not found in initialized threads"

Check available judges with:
```bash
python query_judges.py --list
```

### OpenAI API errors

Ensure your API key is set:
```bash
echo $OPENAI_API_KEY
```

Check your OpenAI account has sufficient credits.

## Example Session

```bash
# 1. Initialize all judges
$ python initialize_judges.py
# ... creates judge_threads.json

# 2. Query three judges on constitutional interpretation
$ python query_judges.py -j thomas scalia gorsuch -q "How should we interpret the Second Amendment?"

# 3. Query all judges on a current issue
$ python query_judges.py --all -q "What limits exist on the Commerce Clause?"

# 4. Save important responses
$ python query_judges.py -j roberts -q "Discuss the role of precedent" -o precedent_discussion.json
```

## Future Enhancements

Potential improvements:
- Use OpenAI Assistants API with file uploads for full opinions
- Add vote prediction based on question analysis
- Implement consensus detection across responses
- Add citation extraction from responses
- Create a web interface for queries
- Support for historical justices
- Integration with actual SCOTUS opinion databases

## License

MIT License - See LICENSE file for details
