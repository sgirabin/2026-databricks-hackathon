import streamlit as st

st.write("Streamlit Version:", st.__version__)

with st.container(key="my_test_container"):
    st.write("Hello inside container")
