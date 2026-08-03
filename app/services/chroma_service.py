import re
import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_or_create_collection(
    name="documents"
)


def store_embedding(
    chunk_id,
    document_id,
    chunk_text,
    embedding
):

    collection.upsert(
        ids=[str(chunk_id)],

        embeddings=[embedding],

        documents=[chunk_text],

        metadatas=[
            {
                "document_id": document_id
            }
        ]
    )


def get_collection():
    return collection

search_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# Domain synonyms for common resume sections to boost relevance ranking
DOMAIN_SYNONYMS = {
    "education": ["education", "degree", "diploma", "bachelor", "master", "university", "college", "cgpa", "percentage", "school", "board", "sppu"],
    "skills": ["skills", "technical skills", "languages", "databases", "frameworks", "tools", "python", "java", "sql", "react"],
    "projects": ["projects", "project", "developed", "built", "created", "bot", "application", "system"],
    "internship": ["internship", "internships", "intern", "experience", "work", "developer", "full stack"],
    "experience": ["experience", "internship", "internships", "work", "role", "company"],
    "certifications": ["certifications", "certification", "certificate", "course", "licensed"],
    "awards": ["awards", "achievements", "prize", "winner", "finalist", "hackathon"],
}


def search_documents(
    query: str,
    top_k: int = 3,
    doc_id: int | None = None
):
    # 1. Clean and normalize query (remove punctuation like '?' and extra whitespace)
    cleaned_query = re.sub(r'[^\w\s]', ' ', query).strip().lower()
    if not cleaned_query:
        cleaned_query = query.strip().lower()

    query_words = [w for w in cleaned_query.split() if len(w) > 1]

    # 2. Compute query embedding for semantic search
    query_embedding = search_model.encode(
        cleaned_query if cleaned_query else query
    ).tolist()

    where_clause = None
    if doc_id is not None:
        where_clause = {
            "document_id": doc_id
        }

    # Fetch a wider candidate pool for re-ranking
    candidate_k = max(top_k * 3, 10)

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=candidate_k,
        where=where_clause
    )

    if not results or not results.get("documents") or not results["documents"][0]:
        return results

    documents = results["documents"][0]
    distances = results.get("distances", [[]])[0]
    if not distances:
        distances = [0.0] * len(documents)

    # 3. Hybrid Re-ranking: Combine keyword matching score + vector similarity score
    scored_results = []
    for doc, dist in zip(documents, distances):
        doc_lower = doc.lower()
        keyword_score = 0.0

        # Exact match for full query string
        if cleaned_query and cleaned_query in doc_lower:
            keyword_score += 10.0

        # Individual word matches & domain synonym matches
        for q_word in query_words:
            if q_word in doc_lower:
                keyword_score += 3.0
                for category, synonyms in DOMAIN_SYNONYMS.items():
                    if q_word in category or category in q_word:
                        for syn in synonyms:
                            if syn in doc_lower:
                                keyword_score += 1.0

        similarity_score = 1.0 / (1.0 + dist)
        total_score = (keyword_score * 5.0) + similarity_score
        scored_results.append((total_score, doc))

    # Sort chunks so that query-relevant results are displayed FIRST
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate docs while preserving rank order to prevent duplicate matches
    seen_docs = set()
    top_docs = []
    for _, doc in scored_results:
        normalized_doc = doc.strip()
        if normalized_doc not in seen_docs:
            seen_docs.add(normalized_doc)
            top_docs.append(doc)
        if len(top_docs) == top_k:
            break

    results["documents"] = [top_docs]

    return results