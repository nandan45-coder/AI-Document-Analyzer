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
    "education": [
        "education", "degree", "diploma", "bachelor", "master", "university", "college",
        "cgpa", "percentage", "school", "state board", "board", "sppu", "academic", "qualification",
        "hsc", "ssc", "engineering", "b.e", "b.tech", "m.tech", "b.sc", "m.sc", "aiml", "computer engineering"
    ],
    "skills": [
        "skills", "technical skills", "languages", "databases", "frameworks", "tools",
        "python", "java", "sql", "react", "html", "css", "javascript", "c++", "c", "mysql", "mongodb"
    ],
    "projects": [
        "projects", "project", "developed", "built", "created", "bot", "application", "system", "builder", "chatbot"
    ],
    "internship": [
        "internship", "internships", "intern", "experience", "work", "developer", "full stack", "uptoskill"
    ],
    "experience": [
        "experience", "internship", "internships", "work", "role", "company", "position"
    ],
    "certifications": [
        "certifications", "certification", "certificate", "course", "licensed", "ibm", "linkedin learning"
    ],
    "awards": [
        "awards", "achievements", "prize", "winner", "finalist", "hackathon", "smart robot"
    ],
}

KNOWN_SECTIONS = [
    ("education", ["education", "academic details", "academic background", "qualifications", "academic performance"]),
    ("summary", ["professional summary", "summary", "profile summary", "about me", "objective"]),
    ("skills", ["technical skills", "skills", "key skills", "languages and databases", "tools & technologies"]),
    ("projects", ["projects", "academic projects", "key projects", "personal projects"]),
    ("internship", ["internships", "internship", "work experience", "experience", "employment history"]),
    ("certifications", ["certifications", "courses and certifications", "certifications & courses"]),
    ("awards", ["awards and achievements", "awards & achievements", "achievements", "honors"]),
]


def word_match(word: str, text: str) -> bool:
    """Check if word/phrase matches text using word boundaries (e.g. 'board' won't match 'dashboard')."""
    pattern = rf'\b{re.escape(word)}\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def detect_target_category(cleaned_query: str, query_words: list[str]) -> str | None:
    """Identify if the query targets a specific document category (e.g. education, skills, projects)."""
    for category in DOMAIN_SYNONYMS.keys():
        if word_match(category, cleaned_query):
            return category

    for category, synonyms in DOMAIN_SYNONYMS.items():
        for word in query_words:
            if word == category or any(word_match(word, syn) for syn in synonyms):
                return category
    return None


def extract_relevant_snippet(doc: str, query_words: list[str], target_category: str | None) -> str:
    """
    Extracts only the section or lines relevant to the user query/target category,
    filtering out unrelated content (e.g. removing summary/skills when searching education).
    """
    lines = [line.strip() for line in doc.split('\n') if line.strip()]
    if not lines:
        return doc.strip()

    # Parse chunk into sections based on recognized section headers
    sections = []
    current_sec_category = None
    current_sec_lines = []

    for line in lines:
        line_lower = line.lower()
        matched_category = None

        for cat, synonyms in KNOWN_SECTIONS:
            for syn in synonyms:
                if line_lower == syn or line_lower.startswith(syn + ":") or line_lower.startswith(syn + " "):
                    matched_category = cat
                    break
            if matched_category:
                break

        if matched_category:
            if current_sec_lines:
                sections.append((current_sec_category, current_sec_lines))
            current_sec_category = matched_category
            current_sec_lines = [line]
        else:
            current_sec_lines.append(line)

    if current_sec_lines:
        sections.append((current_sec_category, current_sec_lines))

    # If sections were parsed and we have a specific target category:
    if target_category and len(sections) > 1:
        matching_lines = []
        for sec_cat, sec_lines in sections:
            # Include section if its category matches target or if unlabelled section contains target synonyms
            if sec_cat == target_category:
                matching_lines.extend(sec_lines)
            elif sec_cat is None and any(word_match(w, ' '.join(sec_lines)) for w in DOMAIN_SYNONYMS.get(target_category, [])):
                matching_lines.extend(sec_lines)

        if matching_lines:
            return ' \n'.join(matching_lines)

    # Line-level filtering fallback if no explicit section headers matched
    if target_category or query_words:
        target_synonyms = DOMAIN_SYNONYMS.get(target_category, []) if target_category else []
        search_terms = [t for t in (query_words + target_synonyms) if len(t) > 1]

        matched_lines = []
        for line in lines:
            if any(word_match(term, line) for term in search_terms):
                matched_lines.append(line)

        if matched_lines:
            return ' \n'.join(matched_lines)

    return doc.strip()


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
    target_category = detect_target_category(cleaned_query, query_words)

    # 2. Compute query embedding for semantic search
    query_embedding = search_model.encode(
        cleaned_query if cleaned_query else query
    ).tolist()

    where_clause = None
    if doc_id is not None:
        where_clause = {
            "document_id": doc_id
        }

    # Fetch candidate pool for re-ranking
    candidate_k = max(top_k * 4, 15)

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

    # 3. Hybrid Re-ranking & Strict Relevance Filtering
    scored_results = []
    for doc, dist in zip(documents, distances):
        keyword_score = 0.0

        # Exact match for full query string
        if cleaned_query and word_match(cleaned_query, doc):
            keyword_score += 10.0

        # Individual word matches & domain synonym matches
        for q_word in query_words:
            if word_match(q_word, doc):
                keyword_score += 3.0
                if target_category and target_category in DOMAIN_SYNONYMS:
                    for syn in DOMAIN_SYNONYMS[target_category]:
                        if word_match(syn, doc):
                            keyword_score += 2.0

        # Additional boost if target category domain terms are found in doc
        if target_category and target_category in DOMAIN_SYNONYMS:
            cat_matches = sum(1 for syn in DOMAIN_SYNONYMS[target_category] if word_match(syn, doc))
            if cat_matches > 0:
                keyword_score += cat_matches * 1.5

        # Strict Relevance Filter:
        # If query has specific search terms or target category, skip chunks with 0 keyword/category matches and weak similarity
        if (query_words or target_category) and keyword_score == 0 and dist > 1.1:
            continue

        similarity_score = 1.0 / (1.0 + dist)
        total_score = (keyword_score * 5.0) + similarity_score
        scored_results.append((total_score, doc))

    # Sort chunks by relevance score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # 4. Extract targeted relevant content & deduplicate docs
    seen_docs = set()
    top_docs = []
    for _, doc in scored_results:
        extracted_text = extract_relevant_snippet(doc, query_words, target_category)
        normalized_doc = extracted_text.strip()
        if normalized_doc and normalized_doc not in seen_docs:
            seen_docs.add(normalized_doc)
            top_docs.append(extracted_text)
        if len(top_docs) == top_k:
            break

    results["documents"] = [top_docs]
    return results