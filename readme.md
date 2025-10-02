# Supreme Court Data Collection with CourtListener API

This toolkit fetches Supreme Court opinions, including syllabus, majority opinions, concurrences, and dissents from the CourtListener API.

## Why CourtListener?

CourtListener provides comprehensive Supreme Court data via REST API with structured JSON responses, including case metadata, opinion text, and separate opinions (majority, concurrence, dissent). The API allows 5,000 queries per hour for authenticated users.

## Setup

### 1. Get API Token

1. Create a free account at [CourtListener.com](https://www.courtlistener.com/)
2. Go to your [profile page](https://www.courtlistener.com/profile/)
3. Find your API token in the profile settings
4. Copy the token

### 2. Install Dependencies

```bash
pip install requests pandas matplotlib jupyter
```

### 3. Configure the Client

Edit `courtlistener_client.py` or set your token in the notebook:

```python
API_TOKEN = "your_token_here"
client = CourtListenerClient(API_TOKEN)
```

## Quick Start

### Fetch All 2025 Supreme Court Cases

```python
from courtlistener_client import CourtListenerClient

# Initialize
client = CourtListenerClient("your_token_here")

# Fetch all 2025 cases (saves to JSON automatically)
cases = client.fetch_year(2025)

# Get statistics
stats = client.get_opinion_stats(cases)
print(stats)
```

### Access Case Data

Each case contains:
- **Case metadata**: name, docket number, dates, citations
- **Syllabus**: Official summary
- **Opinions**: List of all opinions with:
  - Type (majority, concurrence, dissent)
  - Author (Justice name)
  - Full text (plain text and HTML)
  - Joined by information

Example:
```python
case = cases[0]
print(f"Case: {case['case_name']}")
print(f"Date: {case['date_filed']}")
print(f"Syllabus: {case['syllabus'][:200]}...")

for opinion in case['opinions']:
    print(f"{opinion['type_label']} by {opinion['author']}")
    print(f"Text length: {len(opinion['plain_text'])} characters")
```

## Data Structure

### Opinion Types

CourtListener groups opinions into clusters, where each cluster represents a case and contains multiple opinions (majority, concurrences, dissents).

The API uses these type codes:
- `010`: Opinion of the Court (Majority)
- `020`: Concurring Opinion
- `030`: Dissenting Opinion
- `025`: Concurrence in Part
- `035`: Dissent in Part
- `040`: Concur/Dissent

### JSON Output Structure

```json
{
  "case_name": "Smith v. Jones",
  "docket_number": "23-1234",
  "date_filed": "2025-06-20",
  "syllabus": "Summary of the case...",
  "citations": ["606 U.S. 123"],
  "opinions": [
    {
      "type": "010",
      "type_label": "Opinion of the Court",
      "author": "Justice Roberts",
      "plain_text": "Full opinion text...",
      "html": "<div>HTML version...</div>"
    },
    {
      "type": "030",
      "type_label": "Dissenting Opinion",
      "author": "Justice Sotomayor",
      "plain_text": "Dissent text..."
    }
  ]
}
```

## API Endpoints Used

The client uses these CourtListener v4 endpoints:

1. **Clusters**: `/api/rest/v4/clusters/`
   - Filtered by court (`scotus`) and date range
   - Returns case metadata and references to opinions

2. **Opinions**: `/api/rest/v4/opinions/`
   - Filtered by cluster ID
   - Returns full text of each opinion

## Rate Limits

Free accounts get 5,000 requests per hour. The client includes delays (0.8 seconds between requests) to stay well under this limit.

For ~60 cases with multiple opinions each:
- Estimated time: 5-10 minutes
- Requests needed: ~200-300

## Advanced Usage

### Filter by Date Range

```python
# Fetch specific months
from datetime import datetime

clusters = client.get_scotus_clusters(2025)
june_cases = [c for c in clusters if c['date_filed'].startswith('2025-06')]
```

### Extract Specific Opinion Types

```python
# Get all dissenting opinions
dissents = []
for case in cases:
    for opinion in case['opinions']:
        if opinion['type_label'] == 'Dissenting Opinion':
            dissents.append({
                'case': case['case_name'],
                'author': opinion['author'],
                'text': opinion['plain_text']
            })
```

### Search Full Text

```python
def search_opinions(cases, keyword):
    results = []
    for case in cases:
        for opinion in case['opinions']:
            if keyword.lower() in opinion.get('plain_text', '').lower():
                results.append({
                    'case': case['case_name'],
                    'opinion_type': opinion['type_label'],
                    'author': opinion['author']
                })
    return results

# Find all opinions mentioning "due process"
due_process_mentions = search_opinions(cases, "due process")
```

## Data Analysis

Use the Jupyter notebook (`courtlistener_notebook.py`) for:
- Statistical analysis
- Visualization of dissent rates
- Justice opinion counts
- Opinion length analysis
- Timeline analysis

## Troubleshooting

### Authentication Errors
- Verify your token is correct
- Check that you included "Token" in the Authorization header
- Make sure you're logged into CourtListener

### Rate Limit Exceeded
- Increase delay between requests
- Check your recent usage at your [profile page](https://www.courtlistener.com/profile/)
- Wait for the hour to reset

### Missing Data
- Some older cases may not have full text
- Syllabus field may be empty for some cases
- Use `extracted_by_ocr` field to check data quality

## Additional Resources

- [CourtListener API Documentation](https://www.courtlistener.com/help/api/)
- [Case Law API Guide](https://www.courtlistener.com/help/api/rest/v3/case-law/)
- [Bulk Data Downloads](https://www.courtlistener.com/help/api/bulk-data/)
- [GitHub: Free Law Project](https://github.com/freelawproject/courtlistener)

## Alternative: Bulk Data

For historical analysis or large datasets, consider using CourtListener's bulk download of all Supreme Court opinions at https://www.courtlistener.com/api/bulk-data/opinions/scotus.tar.gz.

## Support

- [Free Law Project Forum](https://github.com/freelawproject/courtlistener/discussions)
- [Contact Form](https://www.courtlistener.com/contact/)

## License

This code is provided as-is for research and educational purposes. CourtListener data is provided by Free Law Project, a 501(c)(3) non-profit.