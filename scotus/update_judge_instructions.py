"""
Update judge instructions in judge_assistants.json without recreating vector stores.

This script reads the existing judge_assistants.json and updates only the instructions
field for each judge, preserving all vector store IDs and file IDs.
"""

import json
from initialize_judges import create_judge_instructions


def update_instructions():
    """Update instructions for all judges in judge_assistants.json."""
    input_file = "scotus/judge_assistants.json"

    # Load existing judge data
    print("Loading existing judge data...")
    with open(input_file, 'r') as f:
        judge_data = json.load(f)

    print(f"Found {len(judge_data)} judges\n")

    # Update instructions for each judge
    for judge in judge_data:
        judge_name = judge['judge_name']
        print(f"Updating instructions for {judge['judge_title']}...")

        # Update instructions using the current version of create_judge_instructions
        judge['instructions'] = create_judge_instructions(judge_name)

        print(f"  ✓ Updated\n")

    # Save updated data back to file
    with open(input_file, 'w') as f:
        json.dump(judge_data, f, indent=2)

    print("=" * 60)
    print("Instructions update complete!")
    print(f"Updated file: {input_file}")
    print(f"Total judges updated: {len(judge_data)}")
    print("=" * 60)


if __name__ == "__main__":
    update_instructions()
