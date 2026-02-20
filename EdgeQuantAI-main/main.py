import re
import pandas as pd
# import pandas_ta
import yfinance
# from openai import OpenAI
from EdgeQuantAI import StockTechnicalAnalyzer
# from fundamental_analyser import FundamentalAnalyser
from huggingface_hub import InferenceClient
from PIL import Image
import json
import streamlit as st
import os

# import talib  # This must stay here since you want to use it

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(BASE_DIR, "assets", "logo.png")

# ===================== PAGE CONFIG =====================
try:
    icon_image = Image.open(logo_path)
except Exception:
    # Fallback to a string emoji if the file is missing
    icon_image = "📈" 

# 3. Apply to Page Config
st.set_page_config(
    page_title="EdgeQuantAI",
    page_icon=icon_image,  # Use the object, not the path string
    layout="centered"
)
# ===================== LOAD CONFIG =====================
working_dir = os.path.dirname(os.path.abspath(__file__))
config_data = json.load(open(f"{working_dir}/config.json"))\



# Check if we are on Streamlit Cloud (st.secrets) or Local (config.json)

# Get absolute path of current file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "config.json")

API_KEY = None

# 1️⃣ Try Streamlit Secrets (Cloud)
try:
    API_KEY = st.secrets.get("API_KEY")
except Exception:
    API_KEY = None

# 2️⃣ Fallback to local config.json (Codespaces / local dev)
if not API_KEY and os.path.exists(config_path):
    try:
        with open(config_path) as f:
            config_data = json.load(f)
            API_KEY = config_data.get("API_KEY")
    except Exception:
        pass

# 3️⃣ Final validation
if not API_KEY:
    st.error("API Key not found. Set it in Streamlit Secrets or config.json")
    st.stop()

# 4️⃣ Correct header format for Hugging Face router
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# API_KEY = config_data["Hugging_face"]

# client = OpenAI(api_key=API_KEY)
analyzer = StockTechnicalAnalyzer()
client = InferenceClient(api_key=API_KEY)


# ===================== HEADER =====================
st.image(icon_image, width=100)

st.markdown(
    "<h1 style='text-align:center;'>EdgeQuantAI</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p style='text-align:center; color:#9AA0A6;'>AI-powered technical insights for Indian equities</p>",
    unsafe_allow_html=True
)

st.divider()

# ===================== SESSION STATE =====================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ===================== LOAD NSE SYMBOLS =====================
@st.cache_data
def load_nse_symbols():
    # df = pd.read_csv("assets/nse_symbols.csv")
    # Recommended for the CSV
    csv_path = os.path.join(working_dir, "assets", "nse_symbols.csv")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.upper()

    if "SYMBOL" not in df.columns:
        raise ValueError(f"CSV must contain SYMBOL column. Found: {list(df.columns)}")

    return set(df["SYMBOL"].astype(str).str.upper())

NSE_SYMBOLS = load_nse_symbols()

# ===================== SYMBOL EXTRACTION =====================
def extract_nse_symbols(user_input: str, nse_symbols: set):
    if not user_input:
        return []

    text = user_input.upper()
    tokens = re.findall(r"\b[A-Z]{2,15}\b", text)
    matches = [t for t in tokens if t in nse_symbols]

    return matches

# ===================== SHOW CHAT HISTORY =====================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===================== USER INPUT =====================
user_input = st.chat_input(
    "Ask anything, or type a stock symbol (e.g. INFY, TCS, WIPRO)"
)

# ===================== MAIN LOGIC =====================
if user_input:
    # ---- show & store user message ----
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    matches = extract_nse_symbols(user_input, NSE_SYMBOLS)

    with st.spinner("Thinking..."):
        try:
            # ============ SINGLE STOCK MODE ============
            if len(matches) == 1:
                symbol = matches[0]

                prompt_df = analyzer.main([symbol])

                if prompt_df is None or getattr(prompt_df, "empty", False):
                    assistant_response = f"⚠️ No technical data available for **{symbol}**."
                else:
                    prompt = analyzer.build_prompt(prompt_df, symbol)

                    response = client.chat.completions.create(
                        model="meta-llama/Llama-3.1-8B-Instruct",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert Technical Analyst specializing in Indian equities."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=0.3
                    )

                    assistant_response = response.choices[0].message.content

            # ============ MULTI STOCK MODE ============
            elif len(matches) > 1:
                assistant_response = (
                    f"I detected multiple stocks: **{', '.join(matches)}**.\n\n"
                    "🔧 Comparison mode is coming soon."
                )

            # ============ NORMAL CHAT MODE ============
            else:
                response = client.chat_completion(
                    model="meta-llama/Llama-3.1-8B-Instruct",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a friendly data analyst and mentor."
                        },
                        *st.session_state.messages
                    ],
                    temperature=0.7
                )

                assistant_response = response.choices[0].message.content

        except Exception as e:
            assistant_response = f"❌ Error: {str(e)}"

    # ---- show & store assistant response ----
    st.chat_message("assistant").markdown(assistant_response)
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_response}
    )






