import json
import requests

from google import genai
from google.genai import types
import streamlit as st

# Setup page
st.set_page_config(
    page_title="Free Open-Source Tender Estimator", layout="wide"
)
st.title("🏗️ Free Multi-View AI Tender Estimator")
st.caption(
    "Combines Satellite Aerial View + Optional Front Elevation View (Zero-Cost)"
)

# Sidebar configuration
with st.sidebar:
    st.header("1. Setup & Rates")
    gemini_key = st.text_input(
        "Free Gemini API Key:", type="password", help="From aistudio.google.com"
    )

    st.subheader("Contractor Rate Matrix")
    base_rate = st.number_input("Base Rate per Meter ($)", value=6.00)
    story_2_mult = st.number_input("2-Story Multiplier", value=1.20)
    story_3_mult = st.number_input("3+ Story Multiplier", value=1.50)
    access_surcharge = st.number_input("Access Surcharge ($)", value=150.00)

# Main Form
st.subheader("2. Property Information")
col1, col2 = st.columns([2, 1])

with col1:
    address_input = st.text_input(
        "Full Address / Building Name & Postcode:",
        placeholder="e.g. 10 Downing Street, London, SW1A 2AA",
    )
    uploaded_street_view = st.file_uploader(
        "Optional: Drag & Drop Front/Street View Screenshot (Enhances Story & Access Accuracy):",
        type=["jpg", "jpeg", "png"],
    )

with col2:
    scope = st.selectbox(
        "Scope of Work:", ["Gutter Cleaning", "Window Cleaning", "Roof Inspection"]
    )

if st.button("Generate Combined Tender Estimate"):
    if not gemini_key:
        st.error("Please enter your free Gemini API Key in the sidebar.")
    elif not address_input:
        st.warning("Please enter a property address or postcode.")
    else:
        with st.spinner("Processing satellite and street view imagery..."):
            try:
                # 1. Fetch Aerial View automatically via OpenStreetMap & Esri
                headers = {"User-Agent": "FreeTenderEstimatorApp/1.0"}
                geo_url = f"https://nominatim.openstreetmap.org/search?q={address_input}&format=json&limit=1"
                geo_res = requests.get(geo_url, headers=headers).json()

                if not geo_res:
                    st.error("Address not found. Please check spelling.")
                else:
                    lat, lon = geo_res[0]["lat"], geo_res[0]["lon"]
                    delta = 0.0008
                    bbox = f"{float(lon)-delta},{float(lat)-delta},{float(lon)+delta},{float(lat)+delta}"
                    esri_url = f"https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox={bbox}&bboxSR=4326&size=800,600&imageSR=4326&format=png&f=image"

                    aerial_bytes = requests.get(esri_url).content

                    # Display images on screen
                    img_col1, img_col2 = st.columns(2)
                    with img_col1:
                        st.image(
                            aerial_bytes,
                            caption="Top View: Aerial Satellite (Perimeter)",
                            use_container_width=True,
                        )

                    contents_payload = [
                        types.Part.from_bytes(
                            data=aerial_bytes, mime_type="image/png"
                        )
                    ]

                    if uploaded_street_view is not None:
                        street_bytes = uploaded_street_view.read()
                        with img_col2:
                            st.image(
                                street_bytes,
                                caption="Front View: Uploaded Elevation (Stories & Access)",
                                use_container_width=True,
                            )
                        contents_payload.append(
                            types.Part.from_bytes(
                                data=street_bytes,
                                mime_type=uploaded_street_view.type,
                            )
                        )

                    # 2. Configure AI Client & Prompt
                    client = genai.Client(api_key=gemini_key)
                    rate_card = {
                        "base_rate_per_meter": base_rate,
                        "story_multipliers": {
                            "1": 1.0,
                            "2": story_2_mult,
                            "3+": story_3_mult,
                        },
                        "access_surcharge": access_surcharge,
                    }

                    prompt = f"""
                    You are an expert procurement estimator analyzing images for property at {address_input}.
                    Scope: {scope}.
                    Rate Matrix Rules: {json.dumps(rate_card)}.

                    Instructions:
                    1. Use the Aerial View photo to calculate exact roof perimeter length in meters.
                    2. Use the Front Elevation/Street View photo (if provided) to accurately count the stories, property type, and detect access obstacles (scaffolding requirements, conservatories, trees).
                    3. Calculate the total job tender cost based on the unit rates.

                    Return ONLY JSON format with keys:
                    {{
                        "estimated_stories": str or int,
                        "estimated_perimeter_meters": float,
                        "access_issues_detected": bool,
                        "access_issues_notes": "description",
                        "calculation_breakdown": "step by step math",
                        "total_estimated_price": float
                    }}
                    """

                    contents_payload.insert(0, prompt)

                    # Use standard current Flash model
                    ai_response = client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=contents_payload,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        ),
                    )

                    result = json.loads(ai_response.text)

                    # 3. Display Results
                    st.success("Analysis Complete!")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Est. Stories", result["estimated_stories"])
                    m2.metric(
                        "Est. Perimeter",
                        f"{result['estimated_perimeter_meters']} m",
                    )
                    m3.metric(
                        "Total Quote Price",
                        f"${result['total_estimated_price']:.2f}",
                    )

                    st.subheader("Itemized Breakdown & Reasoning")
                    st.write(result["calculation_breakdown"])
                    if result["access_issues_detected"]:
                        st.warning(
                            f"Access Flag: {result['access_issues_notes']}"
                        )

            except Exception as e:
                st.error(f"An error occurred: {e}")
