"""
Initialize 9 Supreme Court Judge AI Agents using OpenAI Responses API.

This version uses the Responses API with GPT-5 models and vector stores for file search.
"""

import os
import json
import glob
from openai import OpenAI
from typing import Dict, List

# Load environment variables from .env file manually
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip().strip("'").strip('"')
                os.environ[key] = value

# Initialize OpenAI client
client = OpenAI()

# List of all 9 current Supreme Court justices
JUDGES = [
    "alito",
    "barrett",
    "gorsuch",
    "jackson",
    "kagan",
    "kavanaugh",
    "roberts",
    "sotomayor",
    "thomas"
]


def load_judge_documents(judge_name: str) -> Dict[str, List[Dict]]:
    """Load all case documents for a specific judge."""
    scotus_dir = "scotus/data"

    # Find all opinion files for this judge
    opinion_files = glob.glob(f"{scotus_dir}/*_{judge_name}_*.json")
    opinions = []

    for file_path in opinion_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            opinions.append({
                'file': os.path.basename(file_path),
                'case_number': data.get('case_number', ''),
                'opinion_type': data.get('opinion_type', ''),
                'text': data.get('text', '')
            })

    # Find all unique case numbers for this judge
    case_numbers = set()
    for opinion in opinions:
        if opinion['case_number']:
            case_numbers.add(opinion['case_number'])

    # Load syllabi for these cases
    syllabi = []
    for case_num in case_numbers:
        syllabus_file = f"{scotus_dir}/{case_num}_syllabus.json"
        if os.path.exists(syllabus_file):
            with open(syllabus_file, 'r') as f:
                data = json.load(f)
                syllabi.append({
                    'case_number': case_num,
                    'syllabus': data.get('syllabus', '')
                })

    return {
        'opinions': opinions,
        'syllabi': syllabi
    }


def create_judge_instructions(judge_name: str) -> str:
    """Create concise instructions for the judge."""
    return f"""You are Justice {judge_name.title()} of the United States Supreme Court.

ROLE:
- Respond to legal questions from Justice {judge_name.title()}'s perspective
- Use the judicial philosophy and reasoning patterns from your written opinions
- Apply the same interpretive methods and analytical framework you demonstrate in your cases

INSTRUCTIONS:
1. Base responses on principles shown in your opinions
2. Maintain consistency with your demonstrated judicial philosophy
4. Be thoughtful, analytical, and grounded in legal reasoning
5. If the question is outside your opinion coverage, its ok to say "need more grounding data"

You embody Justice {judge_name.title()}'s judicial reasoning style.

The input is always prefixed with "can you decide if this is constitutional, follows federal law, procedural legal and respects power balance and individual rights?"

The output structure should on the first line write these three component.  The first line should be the summary judgment which must be one of three: Support, Overturn, Remand.
The second line should be Certainty: [Definitive | Likely | Qualified | Conditional] and Scope: [Broad | Narrow | Facial | As-Applied]
Then a explanation 2-4 paragraph (300-600 words) covering things like: 
    - Core reasoning
    - Primary constitutional doctrine/framework applied
    - Key precedents cited
    - Any limiting principles or boundaries
    - Others as appropriate

"""


def create_knowledge_document(judge_name: str, documents: Dict) -> str:
    """Create a comprehensive knowledge document with all opinions."""
    content = f"# Justice {judge_name.title()} - Judicial Opinions and Case Context\n\n"

    # Add case syllabi
    content += "## Case Summaries\n\n"
    for syllabus in documents['syllabi']:
        content += f"### Case {syllabus['case_number']}\n\n"
        content += f"{syllabus['syllabus']}\n\n"
        content += "---\n\n"

    # Add opinions
    content += "## Written Opinions\n\n"
    for opinion in documents['opinions']:
        content += f"### Case {opinion['case_number']} - {opinion['opinion_type'].upper()}\n\n"
        content += f"{opinion['text']}\n\n"
        content += "---\n\n"

    return content


def initialize_judge_vector_store(judge_name: str) -> Dict:
    """Create a vector store for a judge's knowledge base."""
    print(f"Initializing {judge_name.title()}...")

    # Load documents
    documents = load_judge_documents(judge_name)
    print(f"  - Loaded {len(documents['opinions'])} opinions")
    print(f"  - Loaded {len(documents['syllabi'])} case syllabi")

    # Create knowledge document
    knowledge_content = create_knowledge_document(judge_name, documents)

    # Save to temporary file
    temp_file = f"temp_{judge_name}_knowledge.txt"
    with open(temp_file, 'w') as f:
        f.write(knowledge_content)

    file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
    print(f"  - Created knowledge document ({file_size_mb:.2f} MB)")

    # Upload file to OpenAI
    with open(temp_file, 'rb') as f:
        file_obj = client.files.create(file=f, purpose='assistants')

    print(f"  - Uploaded to OpenAI (file_id: {file_obj.id})")

    # Create vector store with the file
    vector_store = client.vector_stores.create(
        name=f"Justice {judge_name.title()} Knowledge Base",
        file_ids=[file_obj.id]
    )

    print(f"  - Created vector store (id: {vector_store.id})")

    # Clean up temp file
    os.remove(temp_file)

    print(f"  ✓ Successfully initialized {judge_name.title()}")
    print(f"    Vector Store ID: {vector_store.id}")
    print(f"    File ID: {file_obj.id}")
    print()

    return {
        'judge_name': judge_name,
        'judge_title': f"Justice {judge_name.title()}",
        'vector_store_id': vector_store.id,
        'file_id': file_obj.id,
        'instructions': create_judge_instructions(judge_name),
        'num_opinions': len(documents['opinions']),
        'num_cases': len(documents['syllabi'])
    }


def main():
    """Initialize all 9 judge vector stores."""
    print("=" * 60)
    print("Initializing Supreme Court Judges (Responses API)")
    print("=" * 60)
    print()

    judge_data = []

    for judge in JUDGES:
        try:
            judge_info = initialize_judge_vector_store(judge)
            judge_data.append(judge_info)
        except Exception as e:
            print(f"  ✗ Error initializing {judge}: {str(e)}")
            print()

    # Save judge information
    output_file = "scotus/judge_assistants.json"
    with open(output_file, 'w') as f:
        json.dump(judge_data, f, indent=2)

    print("=" * 60)
    print(f"Initialization complete!")
    print(f"Judge information saved to: {output_file}")
    print(f"Total judges initialized: {len(judge_data)}/9")
    print("=" * 60)


if __name__ == "__main__":
    main()
