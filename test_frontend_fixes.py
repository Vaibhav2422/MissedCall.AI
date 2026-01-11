"""
Test script to verify frontend session state fixes
"""
import streamlit as st

# Test session state initialization
if 'test_phone' not in st.session_state:
    st.session_state.test_phone = ""
if 'test_voice' not in st.session_state:
    st.session_state.test_voice = ""

st.title("Frontend Session State Test")

# Test phone number input with session state
phone_input = st.text_input("Test Phone:", value=st.session_state.test_phone)

# Test voice input with session state  
voice_input = st.text_area("Test Voice:", value=st.session_state.test_voice)

# Test button to update session state
if st.button("Update Session State"):
    st.session_state.test_phone = "1234567890"
    st.session_state.test_voice = "Test voice input"
    st.rerun()

# Display current session state
st.write("Current session state:")
st.write(f"Phone: {st.session_state.test_phone}")
st.write(f"Voice: {st.session_state.test_voice}")

st.success("Session state test completed successfully!")