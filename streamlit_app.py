import streamlit as st

# Define the pages using file paths in pages/ folder
lab1 = st.Page("pages/lab1.py", title="Lab 1", icon="🔬")
lab2 = st.Page("pages/lab2.py", title="Lab 2", icon="🧪", default=True)
lab4 = st.Page("pages/lab4.py", title="Lab 4", icon="🧪")

# Create navigation
pg = st.navigation([lab1, lab2, lab4])

# Run the selected page
pg.run()