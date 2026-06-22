"""
Delete all initialized Supreme Court Judge resources (Responses API version).

This deletes vector stores and files created for the Responses API.
"""

import json
from openai import OpenAI

client = OpenAI()


def delete_judges():
    """Delete all judge vector stores and files."""

    # Load judge data
    try:
        with open("judge_assistants.json", 'r') as f:
            judges = json.load(f)
    except FileNotFoundError:
        print("No judge_assistants.json found. Nothing to delete.")
        return

    print(f"Found {len(judges)} judges to delete.\n")

    for judge in judges:
        judge_name = judge['judge_name']
        judge_title = judge['judge_title']

        print(f"Deleting {judge_title} ({judge_name})...")

        # Delete vector store
        try:
            client.vector_stores.delete(judge['vector_store_id'])
            print(f"  ✓ Deleted vector store: {judge['vector_store_id']}")
        except Exception as e:
            print(f"  ✗ Error deleting vector store: {str(e)}")

        # Delete file
        try:
            client.files.delete(judge['file_id'])
            print(f"  ✓ Deleted file: {judge['file_id']}")
        except Exception as e:
            print(f"  ✗ Error deleting file: {str(e)}")

        print()

    # Delete the JSON file
    import os
    if os.path.exists('judge_assistants.json'):
        os.remove('judge_assistants.json')
        print("✓ Deleted judge_assistants.json")

    print("\n✅ All judges and resources have been deleted!")
    print("You can now run initialize_judges.py to create fresh resources.")


if __name__ == "__main__":
    print("=" * 80)
    print("DELETE SUPREME COURT JUDGE RESOURCES")
    print("=" * 80)
    print("\nThis will delete all judge vector stores and uploaded files.")

    confirm = input("\nAre you sure you want to continue? (yes/no): ")

    if confirm.lower() in ['yes', 'y']:
        print()
        delete_judges()
    else:
        print("\nDeletion cancelled.")
