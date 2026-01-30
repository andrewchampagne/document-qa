# pages/lab2.py
import streamlit as st
from openai import OpenAI

# Show title and description.
st.title("Lab 2")
st.write(
    "Upload a document below and ask a question about it – GPT will answer!"
)

# Sidebar options
st.sidebar.header("Summary Options")

summary_type = st.sidebar.radio(
    "Choose a summary format:",
    [
        "Summarize in 100 words",
        "Summarize in 2 connecting paragraphs",
        "Summarize in 5 bullet points"
    ]
)

use_advanced_model = st.sidebar.checkbox("Use advanced model")
model = "gpt-5-mini" if use_advanced_model else "gpt-5-nano"
st.sidebar.caption(f"Current model: {model}")

# Get API key from Streamlit secrets
# Also made a toml file
openai_api_key = st.secrets["OPENAI_API_KEY"]

try:
    # Create an OpenAI client.
    client = OpenAI(api_key=openai_api_key)
    
    # Let the user upload a file.
    uploaded_file = st.file_uploader(
        "Upload a document (.txt or .md)", type=("txt", "md")
    )

    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="Can you give me a short summary?",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
        # Process the uploaded file and question.
        document = uploaded_file.read().decode()
        
        # Build the prompt based on summary type
        if summary_type == "Summarize in 100 words":
            summary_instruction = "provide your response as a summary in approximately 100 words."
        elif summary_type == "Summarize in 2 connecting paragraphs":
            summary_instruction = "provide your response as a summary in 2 connecting paragraphs."
        else:
            summary_instruction = "provide your response as a summary in 5 bullet points."
        
        messages = [
            {
                "role": "user",
                "content": f"Here's a document: {document} \n\n---\n\n {question} \n\n{summary_instruction}",
            }
        ]

        # Generate an answer using the OpenAI API.
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        # Stream the response to the app using `st.write_stream`.
        st.write_stream(stream)
        
except Exception as e:
    st.error(f"Error: {e}")