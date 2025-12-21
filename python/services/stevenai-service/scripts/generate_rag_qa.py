"""
Generate rag_qa.json from rag_document.json.

Extracts all questions from document metadata and creates QA pairs.
For each entry in rag_document.json (which has content + list of questions),
creates a new entry in rag_qa.json for each question with the content as the answer.
"""

import json
import sys
from pathlib import Path


def generate_rag_qa(doc_path: Path, qa_path: Path):
    """
    Extract QA pairs from rag_document.json.

    Structure:
    - rag_document.json: [{content, metadata: {questions: [...], ...}}]
    - rag_qa.json: [{content: question, metadata: {answer: content, ...}}]
    """
    print(f"Reading documents from: {doc_path}")

    with open(doc_path, 'r', encoding='utf-8') as f:
        documents = json.load(f)

    print(f"Loaded {len(documents)} documents")

    qa_pairs = []

    for doc in documents:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})
        questions = metadata.get("questions", [])

        for question in questions:
            qa_pairs.append({
                "content": question,
                "metadata": {
                    "answer": content,
                    **{k: v for k, v in metadata.items() if k != "questions"}
                }
            })

    print(f"Generated {len(qa_pairs)} QA pairs from documents")

    # Ensure parent directory exists
    qa_path.parent.mkdir(parents=True, exist_ok=True)

    with open(qa_path, 'w', encoding='utf-8') as f:
        json.dump(qa_pairs, f, indent=2, ensure_ascii=False)

    print(f"Saved QA pairs to: {qa_path}")


if __name__ == "__main__":
    # Expects to be run from service root
    doc_path = Path("app/data/rag_document.json")
    qa_path = Path("app/data/rag_qa.json")

    if not doc_path.exists():
        print(f"Error: {doc_path} not found", file=sys.stderr)
        print(f"Please ensure rag_document.json is copied to app/data/", file=sys.stderr)
        sys.exit(1)

    generate_rag_qa(doc_path, qa_path)
    print("✅ Done!")
