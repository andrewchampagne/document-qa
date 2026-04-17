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

    # DEBUG: show what we captured
    st.info(f"DEBUG - User input: {user_input[:100]}")
    st.info(f"DEBUG - Response length: {len(response)} chars")
    st.info(f"DEBUG - Response preview: {response[:200]}")

    # Extract new memories using a cheap model
    existing_memories_text = json.dumps(current_memories) if current_memories else "[]"
    extraction_prompt = (
        "Analyze the following conversation exchange and extract any new facts about the user "
        "worth remembering for future conversations. Look for: name, location, preferences, "
        "interests, hobbies, job, family details, goals, or any other personal information.\n\n"
        f"Existing memories (do NOT duplicate these): {existing_memories_text}\n\n"
        f"User said: {user_input}\n"
        f"Assistant replied: {response}\n\n"
        "Return ONLY a JSON list of short strings for any NEW facts discovered. "
        "If there are no new facts, return an empty list: []\n"
        'Example: ["User\'s name is Alice", "User likes hiking"]\n'
        "Return ONLY valid JSON, no other text."
    )

    try:
        extraction_response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = extraction_response.choices[0].message.content.strip()
        st.info(f"DEBUG - Raw extraction response: {raw}")

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        new_memories = json.loads(raw)
        st.info(f"DEBUG - Parsed memories: {new_memories}")

        if isinstance(new_memories, list) and new_memories:
            current_memories.extend(new_memories)
            save_memories(current_memories)
            st.success(f"DEBUG - Saved {len(new_memories)} new memories! Rerunning...")
            st.rerun()
        else:
            st.warning("DEBUG - No new memories extracted (empty list returned)")

    except json.JSONDecodeError as e:
        st.error(f"DEBUG - JSON parse failed: {e}")
        st.error(f"DEBUG - Raw text was: {raw}")
    except Exception as e:
        st.error(f"DEBUG - Extraction call failed: {type(e).__name__}: {e}")