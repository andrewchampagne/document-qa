from pathlib import Path

import chromadb
import streamlit as st
from openai import OpenAI
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from pypdf import PdfReader


st.title("Lab 4: Build ChromaDB Collection")
st.write(
    "Creates `Lab4Collection` from the 7 syllabus PDFs and stores it in "
    "`st.session_state.Lab4_VectorDB` so embeddings are only computed once per session."
)

PDF_FILENAMES = [
    "IST 195 Syllabus - Information Technologies.pdf",
    "IST 256 Syllabus - Intro to Python for the Information Profession.pdf",
    "IST 314 Syllabus - Interacting with AI.pdf",
    "IST 343 Syllabus - Data in Society.pdf",
    "IST 387 Syllabus - Introduction to Applied Data Science.pdf",
    "IST 418 Syllabus - Big Data Analytics.pdf",
    "IST 488 Syllabus - Building Human-Centered AI Applications.pdf",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "lab4-data"
EMBEDDING_MODEL = "text-embedding-3-small"


def chunk_text(text, chunk_size=1200, overlap=200):
    cleaned_text = " ".join(text.split())
    if not cleaned_text:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    start = 0
    while start < len(cleaned_text):
        chunks.append(cleaned_text[start : start + chunk_size])
        start += step
    return chunks


def read_pdf_as_page_chunks(pdf_path):
    reader = PdfReader(str(pdf_path))
    all_chunks = []

    for page_index, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            continue

        page_chunks = chunk_text(page_text)
        for chunk_index, chunk in enumerate(page_chunks):
            all_chunks.append(
                {
                    "id": f"{pdf_path.name}::p{page_index}::c{chunk_index}",
                    "document": chunk,
                    "metadata": {
                        "source": pdf_path.name,
                        "page_number": page_index,
                        "chunk_index": chunk_index,
                    },
                }
            )

    return all_chunks


def create_lab4_vector_db():
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    embedding_function = OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name=EMBEDDING_MODEL,
    )

    client = chromadb.Client()
    collection = client.get_or_create_collection(
        name="Lab4Collection",
        embedding_function=embedding_function,
    )

    if collection.count() == 0:
        documents = []
        metadatas = []
        ids = []

        for filename in PDF_FILENAMES:
            pdf_path = DATA_DIR / filename
            if not pdf_path.exists():
                st.warning(f"Skipping missing file: {filename}")
                continue

            chunks = read_pdf_as_page_chunks(pdf_path)
            for chunk in chunks:
                ids.append(chunk["id"])
                documents.append(chunk["document"])
                metadatas.append(chunk["metadata"])

        if documents:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)

    return collection


if "Lab4_VectorDB" not in st.session_state:
    with st.spinner("Building Lab4Collection from PDFs..."):
        st.session_state.Lab4_VectorDB = create_lab4_vector_db()

collection = st.session_state.Lab4_VectorDB
st.success("Lab4Collection is ready in st.session_state.Lab4_VectorDB")
st.write(f"Collection name: `{collection.name}`")
st.write(f"Document chunks stored: `{collection.count()}`")


def retrieve_relevant_chunks(query_text, k=5):
    query_result = collection.query(
        query_texts=[query_text],
        n_results=k,
        include=["metadatas", "documents", "distances"],
    )

    metadatas = query_result.get("metadatas", [[]])[0]
    documents = query_result.get("documents", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    chunks = []
    for metadata, document, distance in zip(metadatas, documents, distances):
        chunks.append(
            {
                "source": metadata.get("source", "Unknown"),
                "page_number": metadata.get("page_number", "Unknown"),
                "chunk_text": document,
                "distance": distance,
            }
        )
    return chunks


def build_rag_context(chunks):
    context_blocks = []
    unique_sources = []

    for idx, chunk in enumerate(chunks, start=1):
        source = chunk["source"]
        if source not in unique_sources:
            unique_sources.append(source)
        context_blocks.append(
            f"[Context {idx}] Source: {source} (Page {chunk['page_number']})\n"
            f"{chunk['chunk_text']}"
        )

    return "\n\n".join(context_blocks), unique_sources


st.divider()
st.subheader("Lab 4 RAG Chatbot")
st.write(
    "Ask a question about the syllabus documents. The bot will retrieve relevant "
    "chunks from ChromaDB and use them in the LLM prompt."
)

openai_api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=openai_api_key)

if "lab4_messages" not in st.session_state:
    st.session_state.lab4_messages = []

for message in st.session_state.lab4_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_question := st.chat_input("Ask about the 7 syllabus documents"):
    st.session_state.lab4_messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    retrieved_chunks = retrieve_relevant_chunks(user_question, k=5)
    rag_context, sources_used = build_rag_context(retrieved_chunks)
    rag_used = bool(rag_context.strip())

    system_prompt = (
        "You are a helpful course assistant. Answer using the retrieved syllabus "
        "context when relevant. If the context is insufficient, say so and then "
        "provide your best general guidance.\n\n"
        "You must start your answer with exactly one of:\n"
        "- RAG Status: Using retrieved syllabus context.\n"
        "- RAG Status: No relevant retrieved syllabus context found.\n"
    )

    user_prompt = (
        f"Question:\n{user_question}\n\n"
        f"Retrieved context:\n{rag_context if rag_used else 'None'}\n\n"
        "If you used retrieved context, cite source filenames in a short "
        "'Sources used:' line at the end."
    )

    with st.chat_message("assistant"):
        try:
            completion = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            assistant_text = completion.choices[0].message.content or ""
            st.markdown(assistant_text)
            if rag_used and sources_used:
                st.caption(f"Retrieved from ChromaDB: {', '.join(sources_used)}")
            st.session_state.lab4_messages.append(
                {"role": "assistant", "content": assistant_text}
            )
        except Exception as exc:
            st.error(f"Error generating response: {exc}")