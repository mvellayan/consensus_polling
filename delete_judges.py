"""
Delete all initialized Supreme Court Judge AI Assistants and their resources.
"""

import json
from openai import OpenAI

client = OpenAI()


def delete_judges():
    """Delete all judge assistants, threads, and files."""

    # Load judge assistants
    try:
        with open("judge_assistants.json", 'r') as f:
            assistants = json.load(f)
    except FileNotFoundError:
        print("No judge_assistants.json found. Nothing to delete.")
        return

    print(f"Found {len(assistants)} judges to delete.\n")

    for judge in assistants:
        judge_name = judge['judge_name']
        judge_title = judge['judge_title']

        print(f"Deleting {judge_title} ({judge_name})...")

        # Delete thread
        try:
            client.beta.threads.delete(judge['thread_id'])
            print(f"  ✓ Deleted thread: {judge['thread_id']}")
        except Exception as e:
            print(f"  ✗ Error deleting thread: {str(e)}")

        # Delete assistant
        try:
            client.beta.assistants.delete(judge['assistant_id'])
            print(f"  ✓ Deleted assistant: {judge['assistant_id']}")
        except Exception as e:
            print(f"  ✗ Error deleting assistant: {str(e)}")

        # Delete file
        try:
            client.files.delete(judge['file_id'])
            print(f"  ✓ Deleted file: {judge['file_id']}")
        except Exception as e:
            print(f"  ✗ Error deleting file: {str(e)}")

        print()

    # Delete the JSON files
    import os

    files_to_delete = ['judge_assistants.json', 'judge_threads.json']

    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)
            print(f"✓ Deleted {file}")

    print("\n✅ All judges and resources have been deleted!")
    print("You can now run initialize_judges.py to create fresh assistants.")


if __name__ == "__main__":
    print("=" * 80)
    print("DELETE SUPREME COURT JUDGE AI ASSISTANTS")
    print("=" * 80)
    print("\nThis will delete all judge assistants, threads, and uploaded files.")

    confirm = input("\nAre you sure you want to continue? (yes/no): ")

    if confirm.lower() in ['yes', 'y']:
        print()
        delete_judges()
    else:
        print("\nDeletion cancelled.")
