# Initialize Judges Technical Documentation

## Overview
The `initialize_judges.py` script creates AI representations of all 9 current Supreme Court Justices using OpenAI's Responses API with vector stores for Retrieval-Augmented Generation (RAG).

**Note:** This system uses the **Responses API** (not the Assistants API). Vector stores are created during initialization, and responses are generated on-demand using the file search tool.

## Architecture

### RAG Implementation
- **Vector Database**: OpenAI's managed vector stores (not local)
- **Retrieval**: File search tool with vector similarity matching
- **Generation**: GPT-5 models (gpt-5-nano default; supports gpt-5, gpt-5-mini, gpt-5-nano)
- **Augmentation**: Real judicial opinions and case syllabi enhance responses
- **Reasoning**: Medium effort setting for balanced quality and performance

### Vector Database Details
- **Provider**: OpenAI Vector Stores (cloud-managed)
- **Storage**: Each judge gets a dedicated vector store
- **Content**: Judicial opinions + case syllabi as searchable embeddings
- **Access**: Via OpenAI's file search tool during inference

## Data Pipeline

### 1. Data Loading
```
scotus/ directory structure:
├── {case_number}_{judge_name}_{opinion_type}.json  # Individual opinions
└── {case_number}_syllabus.json                     # Case summaries
```

**Loading Process:**
- Scans `scotus/data/` directory for judge-specific opinion files
- Pattern: `*_{judge_name}_*.json` (e.g., `12345_roberts_majority.json`)
- Loads corresponding case syllabi using case numbers
- Combines opinions with case context

### 2. Data Processing & Sorting
**Document Structure:**
```json
{
  "opinions": [
    {
      "file": "filename.json",
      "case_number": "12-345",
      "opinion_type": "majority|dissent|concurrence",
      "text": "full opinion text"
    }
  ],
  "syllabi": [
    {
      "case_number": "12-345", 
      "syllabus": "case summary"
    }
  ]
}
```

**Content Organization:**
- Groups by judge name (9 separate knowledge bases)
- Sorts by case number for syllabi matching
- Combines case context + judicial opinions
- Creates comprehensive knowledge documents

### 3. Knowledge Document Creation
**Format:**
```markdown
# Justice {Name} - Judicial Opinions and Case Context

## Case Summaries
### Case {number}
{syllabus text}

## Written Opinions  
### Case {number} - {OPINION_TYPE}
{full opinion text}
```

### 4. Vector Store Creation
**Process:**
1. Create temporary text file with all judge content
2. Upload file to OpenAI Files API
3. Create vector store with uploaded file
4. OpenAI automatically creates embeddings
5. Clean up temporary files

## Judge ID Storage

### Primary Storage: `judge_assistants.json`
```json
[
  {
    "judge_name": "roberts",
    "judge_title": "Justice Roberts", 
    "vector_store_id": "vs_abc123",
    "file_id": "file_xyz789",
    "instructions": "system prompt",
    "num_opinions": 45,
    "num_cases": 32
  }
]
```

**Key Identifiers:**
- **`vector_store_id`**: OpenAI vector store identifier for RAG retrieval
- **`file_id`**: OpenAI file identifier for the knowledge document
- **`judge_name`**: Internal identifier (lowercase)
- **`judge_title`**: Display name for UI

## AI Model Configuration

### Model Selection
**Available Models:**
- **gpt-5-nano** (default): Fastest, most cost-effective for high-volume queries
- **gpt-5-mini**: Balanced performance and quality
- **gpt-5**: Highest quality, most thorough analysis

**Reasoning Configuration:**
- **Effort Level**: Medium (balances quality with response time)

### Response Structure
**Structured Output Format:**
```
Outcome: [Strike Down | Uphold | Remand | Dismiss - Jurisdictional | Dismiss - Political Question]
Certainty: [Definitive | Likely | Qualified | Conditional]
Scope: [Broad | Narrow | Facial | As-Applied]

[2-4 paragraph explanation covering constitutional doctrine, precedents, reasoning]
```

**Response Constraints:**
- Maximum 2000 characters for concise, focused analysis
- 300-600 word explanations (2-4 paragraphs)

### Instructions Template
Each judge receives personalized instructions:
- Role-specific judicial philosophy
- Consistency with historical opinions
- Analytical framework matching their style
- Structured response format requirements
- Character limit enforcement for conciseness

## Technical Implementation

### Dependencies
- **OpenAI Python SDK**: API interactions
- **File System**: Local document loading
- **JSON**: Data serialization
- **Glob**: Pattern-based file discovery

### Error Handling
- Individual judge initialization failures don't stop the process
- Temporary file cleanup on completion
- Progress logging for each judge

### Resource Management
- Temporary files created and cleaned up per judge
- File size monitoring (reports MB for each knowledge base)
- Batch processing of all 9 judges

## Output Artifacts

1. **`judge_assistants.json`**: Complete judge configuration
2. **OpenAI Vector Stores**: 9 separate knowledge bases
3. **OpenAI Files**: Uploaded knowledge documents
4. **Console Logs**: Initialization progress and statistics

## Usage in Application

### Query Process
The application uses OpenAI's **Responses API** to query judges:
1. Load judge configuration from `judge_assistants.json`
2. Create response with:
   - Selected model (default: gpt-5-nano)
   - Judge-specific instructions
   - File search tool enabled with judge's vector store
   - Medium reasoning effort
3. OpenAI retrieves relevant context from vector store
4. Model generates response based on judge's opinions and reasoning style

### Configuration Loading
The generated `judge_assistants.json` is used by the main application to:
- Load judge configurations at startup
- Access vector store IDs for RAG queries
- Display judge titles in the UI
- Apply judge-specific instructions during inference
- Enforce response format and character limits

## Performance Characteristics
- **Initialization**: One-time setup process
- **Storage**: Cloud-managed vector databases
- **Retrieval**: Sub-second similarity search
- **Generation**: GPT-5-nano (default) inference with retrieved context and medium reasoning effort
- **Scalability**: Handles large judicial opinion corpora efficiently
- **Model Flexibility**: Supports switching between gpt-5, gpt-5-mini, and gpt-5-nano at query time
