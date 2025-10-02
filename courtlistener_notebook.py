# CourtListener Supreme Court Data Analysis
# Jupyter Notebook for analyzing SCOTUS opinions

# %% Setup and Installation
"""
First, install required packages:
pip install requests pandas matplotlib
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from courtlistener_client import CourtListenerClient  # Import the client we created

# %% Initialize Client
"""
Get your API token from: https://www.courtlistener.com/profile/
After creating a free account, find your token under your profile settings.
"""

API_TOKEN = "YOUR_API_TOKEN_HERE"
client = CourtListenerClient(API_TOKEN)

# %% Fetch 2025 Cases
"""
This will fetch all Supreme Court cases from 2025.
Note: This may take several minutes depending on the number of cases.
The rate limit is 5000 requests/hour, so we add delays between requests.
"""

cases_2025 = client.fetch_year(2025, save_to_file=True, filename='scotus_2025_complete.json')
print(f"Fetched {len(cases_2025)} cases")

# %% Load Previously Saved Data
"""
If you've already fetched the data, you can load it from the JSON file:
"""

with open('scotus_2025_complete.json', 'r', encoding='utf-8') as f:
    cases_2025 = json.load(f)

# %% Convert to DataFrame for Analysis

# Create a DataFrame of cases
cases_df = pd.DataFrame([
    {
        'case_name': case['case_name'],
        'case_name_short': case['case_name_short'],
        'date_filed': case['date_filed'],
        'date_argued': case['date_argued'],
        'docket_number': case['docket_number'],
        'num_opinions': len(case['opinions']),
        'has_dissent': any('Dissent' in op['type_label'] for op in case['opinions']),
        'has_concurrence': any('Concur' in op['type_label'] for op in case['opinions']),
        'syllabus_length': len(case.get('syllabus', '') or ''),
        'cluster_id': case['cluster_id'],
        'url': case['absolute_url']
    }
    for case in cases_2025
])

# Convert date columns to datetime
cases_df['date_filed'] = pd.to_datetime(cases_df['date_filed'])
cases_df['date_argued'] = pd.to_datetime(cases_df['date_argued'])

print(cases_df.head())

# %% Create DataFrame of Individual Opinions

opinions_data = []
for case in cases_2025:
    for opinion in case['opinions']:
        opinions_data.append({
            'case_name': case['case_name_short'],
            'date_filed': case['date_filed'],
            'opinion_type': opinion['type_label'],
            'author': opinion['author'],
            'text_length': len(opinion.get('plain_text', '') or ''),
            'cluster_id': case['cluster_id']
        })

opinions_df = pd.DataFrame(opinions_data)
opinions_df['date_filed'] = pd.to_datetime(opinions_df['date_filed'])

print(f"Total opinions: {len(opinions_df)}")
print(opinions_df.head())

# %% Basic Statistics

stats = client.get_opinion_stats(cases_2025)
print("\nOverall Statistics:")
for key, value in stats.items():
    print(f"{key}: {value}")

# %% Visualize Opinion Types

opinion_type_counts = opinions_df['opinion_type'].value_counts()

plt.figure(figsize=(10, 6))
opinion_type_counts.plot(kind='barh')
plt.title('Distribution of Opinion Types in 2025')
plt.xlabel('Count')
plt.ylabel('Opinion Type')
plt.tight_layout()
plt.show()

# %% Analyze Dissent Rate Over Time

monthly_dissents = cases_df.groupby(cases_df['date_filed'].dt.to_period('M')).agg({
    'has_dissent': 'sum',
    'case_name': 'count'
})
monthly_dissents['dissent_rate'] = monthly_dissents['has_dissent'] / monthly_dissents['case_name']

plt.figure(figsize=(12, 6))
monthly_dissents['dissent_rate'].plot(kind='line', marker='o')
plt.title('Dissent Rate Over Time in 2025')
plt.ylabel('Proportion of Cases with Dissents')
plt.xlabel('Month')
plt.ylim(0, 1)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# %% Most Prolific Opinion Authors

author_counts = opinions_df['author'].value_counts().head(10)

plt.figure(figsize=(10, 6))
author_counts.plot(kind='barh')
plt.title('Top 10 Most Prolific Opinion Authors in 2025')
plt.xlabel('Number of Opinions')
plt.ylabel('Justice')
plt.tight_layout()
plt.show()

# %% Analyze Opinion Length by Type

plt.figure(figsize=(12, 6))
opinions_df.boxplot(column='text_length', by='opinion_type', figsize=(12, 6))
plt.title('Opinion Length Distribution by Type')
plt.suptitle('')  # Remove default title
plt.ylabel('Character Count')
plt.xlabel('Opinion Type')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()

# %% Find Cases with Most Opinions

most_opinions = cases_df.nlargest(10, 'num_opinions')[['case_name_short', 'num_opinions', 'date_filed']]
print("\nCases with Most Opinions:")
print(most_opinions)

# %% Export Data for Further Analysis

# Export cases to CSV
cases_df.to_csv('scotus_2025_cases_summary.csv', index=False)

# Export opinions to CSV
opinions_df.to_csv('scotus_2025_opinions_summary.csv', index=False)

print("Data exported to CSV files")

# %% Full Text Analysis Example
"""
Extract and analyze full text of opinions
"""

# Get all dissenting opinions
dissents = [
    {
        'case': case['case_name_short'],
        'author': opinion['author'],
        'text': opinion.get('plain_text', ''),
        'date': case['date_filed']
    }
    for case in cases_2025
    for opinion in case['opinions']
    if 'Dissent' in opinion['type_label'] and opinion.get('plain_text')
]

print(f"\nFound {len(dissents)} dissenting opinions with text")

# Show first dissent excerpt
if dissents:
    first_dissent = dissents[0]
    print(f"\nFirst dissent: {first_dissent['case']} by {first_dissent['author']}")
    print(f"Text preview: {first_dissent['text'][:500]}...")

# %% Search for Specific Cases or Keywords

def search_cases(cases, keyword):
    """Search for cases containing a keyword in case name or opinions"""
    results = []
    for case in cases:
        # Check case name
        if keyword.lower() in case['case_name'].lower():
            results.append(case)
            continue
        
        # Check opinions
        for opinion in case['opinions']:
            if opinion.get('plain_text') and keyword.lower() in opinion['plain_text'].lower():
                results.append(case)
                break
    
    return results

# Example: Search for cases mentioning "First Amendment"
first_amendment_cases = search_cases(cases_2025, "First Amendment")
print(f"\nCases mentioning 'First Amendment': {len(first_amendment_cases)}")
for case in first_amendment_cases[:5]:
    print(f"  - {case['case_name_short']}")

# %% Create Summary Report

report = f"""
Supreme Court 2025 Analysis Report
==================================

Total Cases: {len(cases_2025)}
Total Opinions: {len(opinions_df)}

Cases by Decision Type:
- With Dissents: {cases_df['has_dissent'].sum()} ({cases_df['has_dissent'].sum()/len(cases_df)*100:.1f}%)
- With Concurrences: {cases_df['has_concurrence'].sum()} ({cases_df['has_concurrence'].sum()/len(cases_df)*100:.1f}%)
- Unanimous: {stats['unanimous_cases']} ({stats['unanimous_cases']/len(cases_df)*100:.1f}%)

Opinion Types:
"""

for op_type, count in stats['opinion_types'].items():
    report += f"- {op_type}: {count}\n"

report += f"\nMost Active Justice (by opinion count): {opinions_df['author'].mode()[0] if len(opinions_df) > 0 else 'N/A'}\n"

print(report)

# Save report
with open('scotus_2025_report.txt', 'w') as f:
    f.write(report)