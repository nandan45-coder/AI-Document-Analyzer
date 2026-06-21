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

    collection.add(
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


def search_documents(
    query,
    top_k=3
):

    query_embedding = search_model.encode(
        query
    ).tolist()

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=top_k
    )

    return results