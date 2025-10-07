"""
Query Supreme Court Judge AI Assistants (FIXED VERSION).

This version properly uses the Assistants API.
"""

import json
import time
from openai import OpenAI
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the same directory as this script
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

client = OpenAI()


def load_judge_assistants() -> Dict[str, Dict]:
    """Load judge assistant information from the saved JSON file."""
    try:
        with open("judge_assistants.json", 'r') as f:
            assistants = json.load(f)
            return {a['judge_name']: a for a in assistants}
    except FileNotFoundError:
        print("Error: judge_assistants.json not found.")
        print("Please run initialize_judges_fixed.py first.")
        exit(1)


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
                # Handle both text and file citations
                text_parts = []
                for content in response_message.content:
                    if hasattr(content, 'text'):
                        text_parts.append(content.text.value)
                return '\n'.join(text_parts)

    return f"Error: Run status was {run.status}"


def query_multiple_judges(judge_names: List[str], question: str) -> Dict[str, str]:
    """Query multiple judges with the same question."""
    judge_assistants = load_judge_assistants()
    responses = {}

    print(f"\nQuestion: {question}\n")
    print("=" * 80)

    for judge_name in judge_names:
        if judge_name not in judge_assistants:
            print(f"\nWarning: Judge '{judge_name}' not found.")
            print(f"Available judges: {', '.join(judge_assistants.keys())}")
            continue

        judge_info = judge_assistants[judge_name]
        print(f"\nQuerying {judge_info['judge_title']}...")

        try:
            response = query_judge(
                judge_name=judge_name,
                assistant_id=judge_info['assistant_id'],
                thread_id=judge_info['thread_id'],
                question=question
            )
            responses[judge_name] = response

            print(f"\n{judge_info['judge_title']} responds:")
            print("-" * 80)
            print(response)
            print("-" * 80)

        except Exception as e:
            print(f"Error querying {judge_name}: {str(e)}")
            responses[judge_name] = f"Error: {str(e)}"

    return responses


def save_responses(question: str, responses: Dict[str, str], output_file: str = None):
    """Save query responses to a JSON file."""
    if output_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"judge_responses_{timestamp}.json"

    output_data = {
        'question': question,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'responses': responses
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n\nResponses saved to: {output_file}")


def main():
    """Main function to query judges."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Query Supreme Court Judge AI Assistants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query specific judges
  python query_judges_fixed.py -j roberts kagan sotomayor -q "What is your view on stare decisis?"

  # Query all judges
  python query_judges_fixed.py --all -q "How should courts interpret the Commerce Clause?"

  # Save output to specific file
  python query_judges_fixed.py -j thomas alito -q "Discuss originalism" -o output.json
        """
    )

    parser.add_argument(
        '-j', '--judges',
        nargs='+',
        help='List of judge names to query (lowercase, e.g., roberts kagan thomas)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Query all 9 judges'
    )

    parser.add_argument(
        '-q', '--question',
        required=True,
        help='Question to ask the judges'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output JSON file path (default: auto-generated with timestamp)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available judges and exit'
    )

    args = parser.parse_args()

    # List judges if requested
    if args.list:
        judge_assistants = load_judge_assistants()
        print("\nInitialized judges:")
        for judge_name, info in judge_assistants.items():
            print(f"  - {info['judge_title']} ({judge_name})")
            print(f"    Cases: {info['num_cases']}, Opinions: {info['num_opinions']}")
            print(f"    Assistant ID: {info['assistant_id']}")
        print()
        return

    # Determine which judges to query
    if args.all:
        judge_assistants = load_judge_assistants()
        judges_to_query = list(judge_assistants.keys())
    elif args.judges:
        judges_to_query = [j.lower() for j in args.judges]
    else:
        parser.error("Either --all or -j/--judges must be specified")

    # Query the judges
    print("=" * 80)
    print("QUERYING SUPREME COURT JUDGES")
    print("=" * 80)

    responses = query_multiple_judges(judges_to_query, args.question)

    # Save responses
    if responses:
        save_responses(args.question, responses, args.output)


if __name__ == "__main__":
    main()
