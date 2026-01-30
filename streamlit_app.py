import streamlit as st
import lab1
import lab2


lab1 = st.Page(lab1.main, title="Lab 1", default=True)
lab2 = st.Page(lab2.main, title="Lab 2")
# Create navigation
pg = st.navigation([lab1, lab2])


pg.run()