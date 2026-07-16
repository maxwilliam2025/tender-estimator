import json
from google import genai
from google.genai import types
import requests
import streamlit as st

# Page setup
st.set_page_config(
    page_title="Free Open-Source Tender Estimator", layout="wide"
)
st.title("🏗️ Free AI Property Tender Estimator")
st.caption("Powered by OpenStreetMap, Esri Imagery, & Gemini AI (Zero-Cost)")

# Sidebar setup for rate card and API key
with st.sidebar:
    st.header("1. API & Rate Configuration")
    gemini_key = st.text_input(
        "Enter Free Gemini API Key:",
        type="password",
        help="Get from aistudio.google.com",
    )

    st.subheader("Contractor Rate Matrix")
    base_rate = st.number_input(
        "Base Rate per Meter ($)", value=6.00, step=0.50
    )
    story_2_mult = st.number_input("2-Story Multiplier", value=1.20, step=0.05)
    story_3_mult = st.number_input("3+ Story Multiplier", value=1.50, step=0.05)
    access_surcharge = st.number_input(
        "Access Issue Surcharge ($)", value=150.00, step=10.00
    )

# Main Form
st.subheader("2. Property Details")
col_a, col_b = st.columns([2, 1])

with col_a:
    address_input = st.text_input(
        "Full Address / Building Name & Postcode:",
        placeholder="e.g. 10 Downing Street, London, SW1A 2AA",
    )
with col_b:
    scope = st.selectbox(
        "Scope of Work:", ["Gutter Cleaning", "Window Cleaning", "Roof Inspection"]
    )

if st.button("Generate Tender Estimate"):
    if not gemini_key:
        st.error("Please enter your free Gemini API Key in the sidebar.")
    elif not address_input:
        st.warning("Please enter a property address or postcode.")
    else:
        with st.spinner("Locating building & pulling open-source satellite data..."):
            try:
                # A. Convert Address to Coordinates using Nominatim (OpenStreetMap)
                headers = {"User-Agent": "FreeTenderEstimatorApp/1.0"}
                geo_url = f"https://nominatim.openstreetmap.org/search?q={address_input}&format=json&limit=1"
                geo_res = requests.get(geo_url, headers=headers).json()

                if not geo_res:
                    st.error(
                        "Address not found. Please provide a more specific address or house number."
                    )
                else:
                    lat = geo_res[0]["lat"]
                    lon = geo_res[0]["lon"]

                    # B. Fetch Aerial Image using Esri World Imagery (No API key needed)
                    # Bounding box calculation for high-res snippet (~100m view)
                    delta = 0.0008
                    bbox = f"{float(lon)-delta},{float(lat)-delta},{float(lon)+delta},{float(lat)+delta}"
                    esri_url = f"https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox={bbox}&bboxSR=4326&size=800,600&imageSR=4326&format=png&f=image"

                    img_bytes = requests.get(esri_url).content

                    # Display image
                    st.image(
                        img_bytes,
                        caption=f"Esri Aerial View of {address_input}",
                        use_container_width=True,
                    )

                    # C. Send Image & Logic to Gemini AI
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
                    Examine this high-resolution satellite/aerial image centered on: {address_input}.
                    Scope of Work: {scope}.
                    Rate Matrix Rules: {json.dumps(rate_card)}.

                    Tasks:
                    1. Identify the target roof footprint in the center. Estimate total perimeter length in meters.
                    2. Estimate estimated height/stories based on roof structure and shadows.
                    3. Check for access difficulties (e.g. glass extensions, tight alleys, tall surrounding trees).
                    4. Apply the rate matrix to calculate the total job quote.

                    Return ONLY a JSON response matching this schema:
                    {{
                        "estimated_stories": int or str,
                        "estimated_perimeter_meters": float,
                        "access_issues_detected": bool,
                        "access_issues_notes": "description of any access obstacles",
                        "calculation_breakdown": "step-by-step math explained",
                        "total_estimated_price": float
                    }}
                    """

                    ai_response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            prompt,
                            types.Part.from_bytes(
                                data=img_bytes, mime_type="image/png"
                            ),
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        ),
                    )

                    # Output Results
                    result = json.loads(ai_response.text)

                    st.success("Tender Estimation Complete!")
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
