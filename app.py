import json
from google import genai
from google.genai import types
import pandas as pd
import streamlit as st

# Streamlit Page Setup
st.set_page_config(
    page_title="Expert Property & Window Cleaning Estimator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏢 Expert Commercial & Residential Property Estimator")
st.caption("AI-Powered Site & Window Cleaning Assessment for Single Operatives (Conservative Time Budgeting)")

# ---------------------------------------------------------
# SIDEBAR: API KEY & ESTIMATION PARAMETERS
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings & Rates")
    gemini_key = st.text_input(
        "Free Gemini API Key:",
        type="password",
        help="Get your free key from aistudio.google.com",
    )

    st.subheader("Base Operative Rates")
    base_ground_mins = st.number_input(
        "Ground Floor (Mins / Window)", value=3.0, step=0.5
    )
    base_upper_mins = st.number_input(
        "Upper Floors (Mins / Window)", value=5.0, step=0.5
    )
    setup_buffer_mins = st.number_input(
        "Fixed Site Setup Buffer (Mins)", value=15.0, step=5.0,
        help="Time for setting up equipment, safety checks, and unpacking gear."
    )

# ---------------------------------------------------------
# MAIN FORM: MULTI-PROPERTY INPUTS
# ---------------------------------------------------------
if "property_count" not in st.session_state:
    st.session_state.property_count = 1

col_top1, col_top2 = st.columns([1, 4])
with col_top1:
    if st.button("➕ Add Another Property"):
        st.session_state.property_count += 1
        st.rerun()

portfolio_inputs = []

for i in range(st.session_state.property_count):
    st.markdown("---")
    st.subheader(f"Property #{i+1}")

    col_a, col_b, col_c = st.columns([2, 1.5, 3])

    with col_a:
        prop_name = st.text_input(
            f"Property Name (Property {i+1}):",
            placeholder="e.g. Oakridge House / Unit B",
            key=f"pname_{i}",
        )
    with col_b:
        postcode = st.text_input(
            f"Postcode (Property {i+1}):",
            placeholder="e.g. SW1A 1AA",
            key=f"postcode_{i}",
        )
    with col_c:
        uploaded_imgs = st.file_uploader(
            f"Upload Property Image(s) (Multiple Allowed):",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True,
            key=f"imgs_{i}",
            help="Upload front, side, and rear photos for higher estimation accuracy.",
        )

    portfolio_inputs.append({
        "id": i + 1,
        "name": prop_name,
        "postcode": postcode,
        "images": uploaded_imgs,
    })

st.markdown("---")

# ---------------------------------------------------------
# PROCESSING LOGIC & AI ESTIMATION
# ---------------------------------------------------------
if st.button("🚀 Calculate Expert Site & Time Estimates"):
    if not gemini_key:
        st.error("Please enter your free Gemini API Key in the left sidebar.")
    else:
        client = genai.Client(api_key=gemini_key)
        results = []

        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, prop in enumerate(portfolio_inputs):
            prop_display = prop["name"] or f"Property #{prop['id']}"
            status_text.text(f"Analyzing {prop_display} ({prop['postcode']})...")

            if not prop["images"]:
                results.append({
                    "Property Name": prop["name"] or f"Property #{prop['id']}",
                    "Postcode": prop["postcode"] or "N/A",
                    "Stories Count": "N/A",
                    "Est. Single Operative Time (Mins)": "N/A",
                    "Est. Time (Hours)": "N/A",
                    "Major Visual Factors & Site Information": "No property photos uploaded for visual analysis.",
                })
            else:
                try:
                    # Package photos for multimodal prompt
                    parts_payload = []
                    for file in prop["images"]:
                        file_bytes = file.read()
                        parts_payload.append(
                            types.Part.from_bytes(
                                data=file_bytes, mime_type=file.type
                            )
                        )

                    # Prompt instructing Gemini as an expert estimator
                    prompt = f"""
                    You are a veteran, master facility estimator and senior operations manager specializing in commercial and residential window cleaning & exterior maintenance.
                    
                    Property Name: "{prop['name']}"
                    Postcode: "{prop['postcode']}"
                    
                    Your Core Mandate:
                    Do NOT under-commit or under-estimate minutes for a single operative working alone. Always budget conservatively to ensure job profitability and safety compliance.

                    Visual Assessment Tasks:
                    1. Count the exact number of stories/floors visible in the property photos.
                    2. Count total window panes (separating ground floor vs upper floors).
                    3. Identify all major building features and site complexity factors from the photos, including:
                       - Window frame types (Georgian mullions, floor-to-ceiling glass, skylights, leaded glass, dormers).
                       - Access issues (high elevation, glass extensions, narrow alleys, overhanging foliage/trees, uneven terrain, sloped roofs).
                       - Equipment requirements (water-fed pole reach, ladder repositioning, safety harness, interior furniture obstacles).
                    
                    Time Calculation Rules (Single Operative):
                    - Ground Floor Base: {base_ground_mins} minutes per window.
                    - Upper Floor Base: {base_upper_mins} minutes per window (accounts for pole/ladder maneuvering).
                    - Fixed Site Setup Buffer: Add {setup_buffer_mins} minutes for unpacking, hose setup, and initial safety walk.
                    - Add additional minute buffers for any detected site complexity, access obstacles, or intricate frame detailing.

                    Return strictly valid JSON matching this schema:
                    {{
                        "stories_count": int or str,
                        "total_window_count": int,
                        "ground_windows": int,
                        "upper_windows": int,
                        "single_operative_time_minutes": float,
                        "single_operative_time_hours": float,
                        "major_building_info_and_factors": "Detailed bulleted list or paragraph highlighting the key visual features, access complexity, equipment needs, and justification for the time estimate."
                    }}
                    """

                    parts_payload.insert(0, prompt)

                    # Call Gemini API
                    ai_response = client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=parts_payload,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        ),
                    )

                    res_json = json.loads(ai_response.text)

                    results.append({
                        "Property Name": prop["name"] or f"Property #{prop['id']}",
                        "Postcode": prop["postcode"] or "N/A",
                        "Stories Count": res_json["stories_count"],
                        "Est. Single Operative Time (Mins)": round(
                            res_json["single_operative_time_minutes"], 1
                        ),
                        "Est. Time (Hours)": round(
                            res_json["single_operative_time_hours"], 2
                        ),
                        "Major Visual Factors & Site Information": res_json[
                            "major_building_info_and_factors"
                        ],
                    })

                except Exception as e:
                    results.append({
                        "Property Name": prop["name"] or f"Property #{prop['id']}",
                        "Postcode": prop["postcode"] or "N/A",
                        "Stories Count": "Error",
                        "Est. Single Operative Time (Mins)": "Error",
                        "Est. Time (Hours)": "Error",
                        "Major Visual Factors & Site Information": f"Analysis failed: {str(e)}",
                    })

            progress_bar.progress((idx + 1) / len(portfolio_inputs))

        status_text.text("Processing complete!")

        # ---------------------------------------------------------
        # DISPLAY RESULTS
        # ---------------------------------------------------------
        st.subheader("📊 Master Estimation Table")
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)

        # Download option
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Full Tender Report as CSV",
            data=csv,
            file_name="expert_property_cleaning_estimates.csv",
            mime="text/csv",
        )
