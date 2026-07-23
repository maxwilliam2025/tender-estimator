import json
import re
import time
from google import genai
from google.genai import types
import streamlit as st

# Streamlit Page Setup
st.set_page_config(
    page_title="Expert Single-Operative Site Estimator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏢 Commercial & Residential Property Estimator")
st.caption(
    "AI-Powered Site & Cleaning Assessment for Single Operatives with Scope Selection"
)

# ---------------------------------------------------------
# SIDEBAR: CONFIGURATION & RATES
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
        "Ground Floor Base (Mins / Unit)", value=3.0, step=0.5
    )
    base_upper_mins = st.number_input(
        "Upper Floors Base (Mins / Unit)", value=5.0, step=0.5
    )
    setup_buffer_mins = st.number_input(
        "Fixed Site Setup Buffer (Mins)",
        value=15.0,
        step=5.0,
        help="Time for setting up equipment, safety checks, and gear unpacking.",
    )

# ---------------------------------------------------------
# MAIN FORM: PROPERTY INPUTS
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

    col_a, col_b, col_c = st.columns([2, 2, 3])

    with col_a:
        prop_name = st.text_input(
            f"Property Name (Property {i+1}):",
            placeholder="e.g. Oakridge House / Unit B",
            key=f"pname_{i}",
        )
        postcode = st.text_input(
            f"Postcode (Property {i+1}):",
            placeholder="e.g. SW1A 1AA",
            key=f"postcode_{i}",
        )
    with col_b:
        scope = st.selectbox(
            f"Scope of Cleaning (Property {i+1}):",
            options=[
                "External windows",
                "Internal windows",
                "External and Internal windows",
                "External and Internal Communals",
                "External Communals",
                "Internal Communals",
            ],
            key=f"scope_{i}",
        )
    with col_c:
        uploaded_imgs = st.file_uploader(
            "Upload Property Image(s) (Multiple Allowed):",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True,
            key=f"imgs_{i}",
            help="Upload front, side, communal areas, and rear photos for higher accuracy.",
        )

    portfolio_inputs.append({
        "id": i + 1,
        "name": prop_name,
        "postcode": postcode,
        "scope": scope,
        "images": uploaded_imgs,
    })

st.markdown("---")

# ---------------------------------------------------------
# PROCESSING & DIRECT ON-SCREEN OUTPUT
# ---------------------------------------------------------
if st.button("🚀 Calculate Expert Site & Time Estimates"):
    if not gemini_key:
        st.error("Please enter your free Gemini API Key in the left sidebar.")
    else:
        client = genai.Client(api_key=gemini_key)

        st.markdown("## 📋 Site Estimation Reports")

        for prop in portfolio_inputs:
            prop_label = (
                prop["name"]
                if prop["name"]
                else f"Property #{prop['id']}"
            )
            postcode_label = (
                f"({prop['postcode']})" if prop["postcode"] else ""
            )

            # Container card for each property report
            with st.container():
                st.markdown(f"### 📍 {prop_label} {postcode_label}")
                st.caption(f"🎯 **Cleaning Scope Selected:** {prop['scope']}")

                if not prop["images"]:
                    st.warning(
                        "⚠️ No images uploaded for this property. Visual analysis could not be performed."
                    )
                else:
                    with st.spinner(
                        f"Analyzing visual factors for {prop_label}..."
                    ):
                        try:
                            # Package images
                            parts_payload = []
                            for file in prop["images"]:
                                file_bytes = file.read()
                                parts_payload.append(
                                    types.Part.from_bytes(
                                        data=file_bytes, mime_type=file.type
                                    )
                                )

                            # Expert Estimator Prompt incorporating scope logic
                            prompt = f"""
                            You are a senior master facility estimator specializing in commercial and residential cleaning.
                            
                            Property Name: "{prop['name']}"
                            Postcode: "{prop['postcode']}"
                            Cleaning Scope Requested: "{prop['scope']}"
                            
                            MANDATE:
                            Do NOT under-commit or under-estimate cleaning minutes for a single operative working alone. Budget conservatively for safety, access difficulty, and job profitability.

                            Scope Rules & Labor Multipliers:
                            - "External windows": Estimate exterior glass surfaces, frame heights, and reach requirements.
                            - "Internal windows": Estimate interior glass access, internal obstacles (blinds, sills, furniture), and indoor gear setup.
                            - "External and Internal windows": Must double the glass surface cleaning work and add internal access maneuver time.
                            - "External Communals": Focus on main entrance glass, communal ground glass, exterior porches, and shared canopy features.
                            - "Internal Communals": Focus on shared stairwells, hallway glazing, entryway double doors, and high-traffic communal glass.
                            - "External and Internal Communals": Combine both internal and external communal entryways, stairwells, and shared glazing.

                            Tasks:
                            1. Count total visible stories/floors.
                            2. Count target glass/window panes relevant to the chosen scope.
                            3. Evaluate visual obstacles: frame types, high reach access, sloping ground, overhangs, staircases, foliage, indoor obstacles, etc.
                            4. Compute single operative time budget:
                               - Ground base rate: {base_ground_mins} mins per window/unit.
                               - Upper base rate: {base_upper_mins} mins per window/unit.
                               - Setup buffer: {setup_buffer_mins} mins base.
                               - Add appropriate minute buffers for the specific selected scope and complexity.

                            Return strictly valid JSON matching this schema:
                            {{
                                "stories_count": int or str,
                                "total_window_count": int,
                                "ground_windows": int,
                                "upper_windows": int,
                                "single_operative_time_minutes": float,
                                "single_operative_time_hours": float,
                                "major_building_info_and_factors": "Detailed explanation highlighting key visual features, chosen scope adjustments, access obstacles, equipment needs, and time justification."
                            }}
                            """

                            parts_payload.insert(0, prompt)

                            # Gemini Call with Retry Logic for Rate Limits
                            ai_response = None
                            for attempt in range(3):
                                try:
                                    ai_response = client.models.generate_content(
                                        model="gemini-3.5-flash",
                                        contents=parts_payload,
                                        config=types.GenerateContentConfig(
                                            response_mime_type="application/json"
                                        ),
                                    )
                                    break
                                except Exception as err:
                                    if "429" in str(err) and attempt < 2:
                                        st.warning(
                                            "⏳ Hit rate limit. Pausing 30 seconds before retrying..."
                                        )
                                        time.sleep(30)
                                    else:
                                        raise err

                            # Clean Regex JSON Extraction
                            raw_text = ai_response.text.strip()
                            match = re.search(r"\{.*\}", raw_text, re.DOTALL)

                            if match:
                                clean_json_str = match.group(0)
                                res = json.loads(clean_json_str)
                            else:
                                res = json.loads(raw_text)

                            # Display Key Metrics on Screen
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Stories / Floors", res["stories_count"])
                            m2.metric(
                                "Target Windows/Units", res["total_window_count"]
                            )
                            m3.metric(
                                "Operative Time (Mins)",
                                f"{round(res['single_operative_time_minutes'], 1)} mins",
                            )
                            m4.metric(
                                "Operative Time (Hours)",
                                f"{round(res['single_operative_time_hours'], 2)} hrs",
                            )

                            # Detailed On-Screen Analysis Box
                            st.markdown(
                                f"**🔍 Expert Site Inspection & Factors ({prop['scope']}):**"
                            )
                            st.info(res["major_building_info_and_factors"])

                        except Exception as e:
                            st.error(
                                f"An error occurred while analyzing {prop_label}: {e}"
                            )

                st.markdown("---")
