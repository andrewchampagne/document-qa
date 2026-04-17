# pages/lab9.py
import streamlit as st
from openai import OpenAI
import json
import os

MEMORY_FILE = "memories.json"

def load_memories():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_memories(memories):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, indent=2)

st.title("Chatbot with Long-Term Memory")
st.write("Chat with an AI that remembers things about you across conversations!")

openai_api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=openai_api_key)

st.sidebar.header("Settings")
use_advanced_model = st.sidebar.checkbox("Use advanced model")
model = "gpt-4.1-mini" if use_advanced_model else "gpt-4.1-nano"
st.sidebar.write(f"Current model: {model}")

st.sidebar.header("Memories")
memories = load_memories()

if memories:
    for i, memory in enumerate(memories):
        st.sidebar.write(f"• {memory}")
    if st.sidebar.button("Clear All Memories"):
        save_memories([])
        st.rerun()
else:
    st.sidebar.write("No memories yet. Start chatting!")

if "lab9_messages" not in st.session_state:
    st.session_state.lab9_messages = []

for message in st.session_state.lab9_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input("Say something..."):
    st.session_state.lab9_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    current_memories = load_memories()
    system_prompt = "You are a friendly and helpful assistant."
    if current_memories:
        memory_text = "\n".join(f"- {m}" for m in current_memories)
        system_prompt += (
            f"\n\nHere are things you remember about this user from past conversations:\n{memory_text}"
            "\n\nUse these memories naturally in conversation when relevant. "
            "For example, greet them by name if you know it."
        )

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(st.session_state.lab9_messages)

    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=api_messages,
                stream=True,
            )
            response_chunks = []
            response_container = st.empty()
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    response_chunks.append(token)
                    response_container.markdown("".join(response_chunks))
            response = "".join(response_chunks)
        except Exception as e:
            response = f"Sorry, I encountered an error: {e}"
            st.error(response)

    st.session_state.lab9_messages.append({"role": "assistant", "content": response})

    existing_memories_text = json.dumps(current_memories) if current_memories else "[]"
    extraction_prompt = f"""You are a memory extraction assistant. Your ONLY job is to find NEW facts about the user from their latest message.

The user's latest message: "{user_input}"

These memories are ALREADY saved (do not repeat any of these):
{existing_memories_text}

Extract ANY new personal facts from the user's message. Look for:
- Name, age, birthday
- School, major, job, career
- Location, hometown
- Hobbies, interests, sports, instruments
- Favorite foods, movies, music, books
- Family, pets, relationships
- Goals, plans, preferences

IMPORTANT: If the user's message contains ANY personal facts not already in the saved memories list above, you MUST extract them. Be thorough. Each fact should be a short sentence.

Return a JSON list of strings. If there are truly no new facts, return [].
Example: ["User is a computer science major", "User's favorite food is salmon"]

Return ONLY the JSON list, nothing else."""

    try:
        extraction_response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = extraction_response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        new_memories = json.loads(raw)
        

        if isinstance(new_memories, list) and new_memories:
            current_memories.extend(new_memories)
            save_memories(current_memories)
            st.rerun()
        else:
            st.warning("No new memories extracted")

    except json.JSONDecodeError as e:
        st.error(f"Failed to parse memories as JSON: {e}")
    except Exception as e:
        st.error(f"Extraction failed: {type(e).__name__}: {e}")