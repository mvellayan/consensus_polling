"""
Query Supreme Court Judge AI using OpenAI Responses API.

This version uses the Responses API with GPT-5 models.
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
    """Load judge information from the saved JSON file."""
    try:
        with open("judge_assistants.json", 'r') as f:
            judges = json.load(f)
            return {j['judge_name']: j for j in judges}
    except FileNotFoundError:
        print("Error: judge_assistants.json not found.")
        print("Please run initialize_judges.py first.")
        exit(1)


def query_judge(judge_name: str, vector_store_id: str, instructions: str, question: str, model: str = "gpt-5-nano") -> str:
    """Send a question to a specific judge and get their response using Responses API."""
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
        return f"Error: {str(e)}"


def query_multiple_judges(judge_names: List[str], question: str, model: str = "gpt-5-nano") -> Dict[str, str]:
    """Query multiple judges with the same question."""
    judge_data = load_judge_assistants()
    responses = {}

    print(f"\nQuestion: {question}\n")
    print("=" * 80)

    for judge_name in judge_names:
        if judge_name not in judge_data:
            print(f"\nWarning: Judge '{judge_name}' not found.")
            print(f"Available judges: {', '.join(judge_data.keys())}")
            continue

        judge_info = judge_data[judge_name]
        print(f"\nQuerying {judge_info['judge_title']}...")

        try:
            response = query_judge(
                judge_name=judge_name,
                vector_store_id=judge_info['vector_store_id'],
                instructions=judge_info['instructions'],
                question=question,
                model=model
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
        description="Query Supreme Court Judge AI using Responses API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query specific judges
  python query_judges.py -j roberts kagan sotomayor -q "What is your view on stare decisis?"

  # Query all judges
  python query_judges.py --all -q "How should courts interpret the Commerce Clause?"

  # Save output to specific file
  python query_judges.py -j thomas alito -q "Discuss originalism" -o output.json

  # Use a different GPT-5 model
  python query_judges.py -j roberts -q "Discuss federalism" --model gpt-5
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

    parser.add_argument(
        '--model',
        default='gpt-5-nano',
        choices=['gpt-5', 'gpt-5-mini', 'gpt-5-nano'],
        help='GPT-5 model to use (default: gpt-5-nano)'
    )

    args = parser.parse_args()

    # List judges if requested
    if args.list:
        judge_data = load_judge_assistants()
        print("\nInitialized judges:")
        for judge_name, info in judge_data.items():
            print(f"  - {info['judge_title']} ({judge_name})")
            print(f"    Cases: {info['num_cases']}, Opinions: {info['num_opinions']}")
            print(f"    Vector Store ID: {info['vector_store_id']}")
        print()
        return

    # Determine which judges to query
    if args.all:
        judge_data = load_judge_assistants()
        judges_to_query = list(judge_data.keys())
    elif args.judges:
        judges_to_query = [j.lower() for j in args.judges]
    else:
        parser.error("Either --all or -j/--judges must be specified")

    # Query the judges
    print("=" * 80)
    print("QUERYING SUPREME COURT JUDGES (Responses API)")
    print("=" * 80)

    responses = query_multiple_judges(judges_to_query, args.question, args.model)

    # Save responses
    if responses:
        save_responses(args.question, responses, args.output)


if __name__ == "__main__":
    main()
