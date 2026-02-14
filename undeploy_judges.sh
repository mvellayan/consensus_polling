export `cat .env`

echo "DEBUG: API Key loaded: ${OPENAI_API_KEY:0:20}..." # Show first 20 chars only

python delete_judges.py

echo "Deleting all vector stores..."
# Get all vector stores and delete them
vs_response=$(curl -s https://api.openai.com/v1/vector_stores \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "OpenAI-Beta: assistants=v2")

echo "DEBUG: Vector stores API response:"
echo "$vs_response" | jq '.'

vector_stores=$(echo "$vs_response" | jq -r '.data[]?.id // empty')

if [ -n "$vector_stores" ]; then
  for vs_id in $vector_stores; do
    echo "Deleting vector store: $vs_id"
    curl -s -X DELETE https://api.openai.com/v1/vector_stores/$vs_id \
      -H "Authorization: Bearer $OPENAI_API_KEY" \
      -H "OpenAI-Beta: assistants=v2"
  done
else
  echo "No vector stores found or already deleted."
fi

echo "Deleting all files..."
# Get all files and delete them
files_response=$(curl -s https://api.openai.com/v1/files \
  -H "Authorization: Bearer $OPENAI_API_KEY")

echo "DEBUG: Files API response:"
echo "$files_response" | jq '.'

files=$(echo "$files_response" | jq -r '.data[]?.id // empty')

if [ -n "$files" ]; then
  for file_id in $files; do
    echo "Deleting file: $file_id"
    curl -s -X DELETE https://api.openai.com/v1/files/$file_id \
      -H "Authorization: Bearer $OPENAI_API_KEY"
  done
else
  echo "No files found or already deleted."
fi

echo "Cleanup complete!"
