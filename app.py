import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn
# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Data Concierge", layout="wide")
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 2. SESSION STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "df" not in st.session_state:
    st.session_state.df = None
if "df_history" not in st.session_state:    
    st.session_state.df_history = []
if "last_uploaded" not in st.session_state:
    st.session_state.last_uploaded = None

# --- 3. SIDEBAR: FILE UPLOADER ---
uploaded_file = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded_file:
    if st.session_state.last_uploaded != uploaded_file.name:
        st.session_state.df = pd.read_csv(uploaded_file)
        st.session_state.last_uploaded = uploaded_file.name
        st.session_state.messages = []
        st.session_state.df_history = []    
    
    # Use the dataframe from session state
    df = st.session_state.df
    
    # Generate Metadata
    metadata = f"Columns: {list(df.columns)}\nTypes: {df.dtypes.to_dict()}\nNulls: {df.isnull().sum().to_dict()}"

    # --- 4. CHAT INTERFACE ---
    st.subheader("💬 Chat with your Data")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ex: 'Drop all rows with missing values'"):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # System Prompt
        system_context = f"""
        You are a Data Preprocessing and Visualization Expert. 
        Dataset Metadata:
        {metadata}
        
        Rules for Data Cleaning:
        1. If modifying data, provide ONE block of Python code using the variable 'df'.
        
        Rules for Visualization:
        1. If the user asks for a chart or plot, use 'matplotlib.pyplot' (as plt) or 'seaborn' (as sns).
        2. You MUST assign the final figure object to a variable named 'fig'. 
           Example: 
           fig, ax = plt.subplots()
           sns.histplot(df['Column'], ax=ax)
        
        General Rules:
        1. Explain what you are doing briefly.
        2. Surround your code in triple backticks: ```python\n<code here>\n```
        3. Do NOT use print() or plt.show().
        """

        full_prompt = f"{system_context}\n\nUser Request: {prompt}"
        response = model.generate_content(full_prompt)
        bot_reply = response.text
        
        # Display Assistant Response
        with st.chat_message("assistant"):
            st.markdown(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply})

        # --- 5. THE MAGIC: EXTRACT AND EXECUTE CODE ---
        # Look for code between ```python and ```
        match = re.search(r'```python\n(.*?)\n```', bot_reply, re.DOTALL)
        
        if match:
            code_to_run = match.group(1)
            try:
                # Save a deep copy of the current dataframe BEFORE executing
                st.session_state.df_history.append(st.session_state.df.copy())
                
                local_vars = {
                    'df': st.session_state.df, 
                    'pd': pd, 
                    'plt': plt, 
                    'sns': sns, 
                    'fig': None
                }
                
                # Execute the code!
                exec(code_to_run, globals(), local_vars)
                
                # --- THE MISSING PIECES ---
                # 1. Overwrite the session state with the newly modified dataframe
                st.session_state.df = local_vars['df']
                
                # 2. Handle Visualization OR Data Updates
                if local_vars.get('fig') is not None:
                    st.success("✨ Chart generated successfully!")
                    st.pyplot(local_vars['fig'])
                else:
                    st.success("✨ Data updated successfully!")
                    st.rerun() # This forces the UI to refresh with the new data
                # --------------------------
                    
            except Exception as e:
                st.error(f"⚠️ Error executing code: {e}")

    # --- 6. DATA PREVIEW ---
   # --- 6. DATA PREVIEW & UNDO ---
    # --- 6. DATA PREVIEW, UNDO & DOWNLOAD ---
    st.divider()
    
    # Create THREE columns: one for the title, one for undo, one for download
    header_col, undo_col, download_col = st.columns([3, 1, 1])
    
    with header_col:
        st.subheader("Current Data State")
        
    with undo_col:
        # Only show the Undo button if we have past states saved
        if len(st.session_state.df_history) > 0:
            if st.button("⏪ Undo Last Action"):
                st.session_state.df = st.session_state.df_history.pop()
                st.session_state.messages.append({"role": "assistant", "content": "⏪ Action undone. Data restored."})
                st.rerun()

    with download_col:
        # Generate the CSV data for download
        if st.session_state.df is not None:
            csv_data = st.session_state.df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Download Clean CSV",
                data=csv_data,
                file_name="cleaned_dataset.csv",
                mime="text/csv"
            )

    # Show the actual data table
    st.dataframe(st.session_state.df.head(10))