from pathlib import Path

import chromadb
import streamlit as st
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


def get_top_3_file_results(query_text):
    query_result = collection.query(
        query_texts=[query_text],
        n_results=12,
        include=["metadatas", "documents", "distances"],
    )

    metadatas = query_result.get("metadatas", [[]])[0]
    documents = query_result.get("documents", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    ordered_files = []
    file_details = {}

    for metadata, document, distance in zip(metadatas, documents, distances):
        source = metadata.get("source", "Unknown")
        if source not in file_details:
            file_details[source] = {
                "distance": distance,
                "sample_text": document,
            }
            ordered_files.append(source)
        if len(ordered_files) == 3:
            break

    return ordered_files, file_details


def quick_relevance_check(query_text, sample_text):
    query_terms = [term.lower() for term in query_text.split() if len(term) > 2]
    sample_lower = (sample_text or "").lower()
    matched_terms = [term for term in query_terms if term in sample_lower]
    return matched_terms


st.divider()
st.subheader("VectorDB Retrieval Test")

test_query = st.selectbox(
    "Pick a test search string",
    ["Generative AI", "Text Mining", "Data Science Overview"],
)
custom_query = st.text_input("Or enter your own search string (optional)")
query_to_run = custom_query.strip() if custom_query.strip() else test_query

if st.button("Run VectorDB Test"):
    top_files, details = get_top_3_file_results(query_to_run)

    st.write(f"Search string: `{query_to_run}`")
    st.write("Top 3 returned documents (ordered):")
    for idx, filename in enumerate(top_files, start=1):
        st.write(f"{idx}. {filename}")

    st.write("Validation (quick check):")
    for filename in top_files:
        sample_text = details[filename]["sample_text"]
        matched_terms = quick_relevance_check(query_to_run, sample_text)
        status = "Seems relevant" if matched_terms else "Review manually"
        st.write(
            f"- {filename}: {status} | matched terms: "
            f"{', '.join(matched_terms) if matched_terms else 'none'}"
        )