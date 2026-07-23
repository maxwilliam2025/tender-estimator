import json
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
    "AI-Powered Site & Window Cleaning Assessment for Single Operatives"
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
        "Ground Floor (Mins / Window)", value=3.0, step=0.5
    )
    base_upper_mins = st.number_input(
        "Upper Floors (Mins / Window)", value=5.0, step=0.5
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
            "Upload Property Image(s) (Multiple Allowed):",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True,
            key=f"imgs_{i}",
            help="Upload front, side, and rear photos for higher accuracy.",
        )

    portfolio_inputs.append({
        "id": i + 1,
        "name": prop_name,
        "postcode": postcode,
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

                            # Expert Estimator Prompt
                            prompt = f"""
                            You are a senior master facility estimator specializing in commercial and residential window cleaning.
                            
                            Property Name: "{prop['name']}"
                            Postcode: "{prop['postcode']}"
                            
                            MANDATE:
                            Do NOT under-commit or under-estimate cleaning minutes for a single operative working alone. Budget conservatively for safety and job profitability.

                            Tasks:
                            1. Count total visible stories/floors.
                            2. Count ground floor windows vs upper floor windows.
                            3. Evaluate visual obstacles: frame types, high reach access, sloping ground, overhangs, glass extensions, foliage, etc.
                            4. Compute single operative time budget:
                               - Ground base: {base_ground_mins} mins/window
                               - Upper base: {base_upper_mins} mins/window
                               - Setup buffer: {setup_buffer_mins} mins
                               - Add relevant minute buffers for complexity.

                            Return strictly valid JSON matching this schema:
                            {{
                                "stories_count": int or str,
                                "total_window_count": int,
                                "ground_windows": int,
                                "upper_windows": int,
                                "single_operative_time_minutes": float,
                                "single_operative_time_hours": float,
                                "major_building_info_and_factors": "Detailed explanation highlighting key features, access obstacles, equipment needs, and time justification."
                            }}
                            """

                            parts_payload.insert(0, prompt)

                            # Gemini Call (using standard supported flash model string)
                            ai_response = client.models.generate_content(
                                model="gemini-3.5-flash",
                                contents=parts_payload,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json"
                                ),
                            )

                            res = json.loads(ai_response.text)

                            # Display Key Metrics on Screen
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Stories / Floors", res["stories_count"])
                            m2.metric(
                                "Total Windows", res["total_window_count"]
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
                                "**🔍 Expert Site Inspection & Major Factors:**"
                            )
                            st.info(res["major_building_info_and_factors"])

                        except Exception as e:
                            st.error(
                                f"An error occurred while analyzing {prop_label}: {e}"
                            )

                st.markdown("---")
