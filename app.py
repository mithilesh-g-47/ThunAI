import streamlit as st
import googlemaps
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import get_geolocation
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client
from datetime import datetime

# Twilio credentials
TWILIO_ACCOUNT_SID = 'ACd393657ea539fc692c97e4346d200148'
TWILIO_AUTH_TOKEN = '30fc0917ed30caca1fe0e39f066a8020'
TWILIO_PHONE_NUMBER = '+12564190840'
POLICE_CONTACT_NUMBER = '+917305588655'

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate('thunai-99dc8-firebase-adminsdk-q5f9q-889676b91f.json')
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Set your Google Maps API key
YOUR_GOOGLE_MAPS_API_KEY = 'AIzaSyDD3k1fw2nnrIpZY-Lq17fJS6rB6ibvNmM'
gmaps = googlemaps.Client(key=YOUR_GOOGLE_MAPS_API_KEY)

# Emergency alert function
def send_emergency_message(emergency_contact, lat, lng):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    google_maps_link = f"https://www.google.com/maps?q={lat},{lng}"
    emergency_message = f"This is an emergency! Help needed at: {google_maps_link}"
    
    try:
        formatted_emergency_contact = f"+91{emergency_contact}"
        client.messages.create(body=emergency_message, from_=TWILIO_PHONE_NUMBER, to=formatted_emergency_contact)
        client.messages.create(body=emergency_message, from_=TWILIO_PHONE_NUMBER, to=POLICE_CONTACT_NUMBER)
        st.success("Emergency message with location sent!")
    except Exception as e:
        st.error(f"Failed to send emergency message: {e}")

# Get location name from coordinates
def get_location_name(lat, lng):
    try:
        result = gmaps.reverse_geocode((lat, lng))
        for component in result[0]['address_components']:
            if 'sublocality' in component['types']:
                return component['long_name']
        for component in result[0]['address_components']:
            if 'locality' in component['types']:
                return component['long_name']
        return result[0]['formatted_address']
    except Exception as e:
        st.error(f"Error fetching location data: {e}")
        return "Error fetching location"

# Search location by name
def search_location(location_name):
    try:
        geocode_result = gmaps.geocode(location_name)
        if geocode_result:
            loc = geocode_result[0]['geometry']['location']
            return loc['lat'], loc['lng'], location_name
        return None, None, "Location not found"
    except Exception as e:
        st.error(f"Error searching for location: {e}")
        return None, None, "Error searching for location"

# Firebase reporting and fetching
def report_incident(location_name, lat, lng, description):
    incident_data = {
        'location_name': location_name, 
        'latitude': lat, 
        'longitude': lng, 
        'description': description, 
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    db.collection('incidents').add(incident_data)

def fetch_incidents():
    incidents_ref = db.collection('incidents')
    incidents = incidents_ref.stream()
    return [{'location_name': inc.to_dict()['location_name'], 'latitude': inc.to_dict()['latitude'], 'longitude': inc.to_dict()['longitude'], 'description': inc.to_dict()['description']} for inc in incidents]

# Forum Functions
def post_message(username, message):
    forum_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now()
    }
    db.collection('forum').add(forum_data)

def fetch_forum_messages():
    forum_ref = db.collection('forum').order_by('timestamp', direction=firestore.Query.ASCENDING)
    messages = forum_ref.stream()
    return [{'username': msg.to_dict()['username'], 'message': msg.to_dict()['message'], 'timestamp': msg.to_dict()['timestamp']} for msg in messages]

# Function to find nearby places
def find_nearby_places(lat, lng, place_type):
    try:
        # Map the user selection to Google Places types
        place_type_mapping = {
            "Police Station": "police",
            "Bus Stop": "bus_station"
        }
        
        # Get the selected place type
        selected_place_type = place_type_mapping.get(place_type)

        # Fetch nearby places with the specified type
        if selected_place_type:
            places_result = gmaps.places_nearby(location=(lat, lng), radius=5000, type=selected_place_type)
            return [{'name': place['name'], 'latitude': place['geometry']['location']['lat'], 'longitude': place['geometry']['location']['lng']} for place in places_result['results']]
        else:
            st.error("Invalid place type selected.")
            return []
    except Exception as e:
        st.error(f"Error fetching nearby places: {e}")
        return []
# App layout
st.title("Thunai")

# Create tabs
tab1, tab2 = st.tabs(["Home", "Forum"])

# Home Tab
with tab1:
    # Single geolocation call
    loc = get_geolocation()
    if loc:
        lat = loc['coords']['latitude']
        lng = loc['coords']['longitude']
        location_name = get_location_name(lat, lng)

        # Emergency contact input with button
        col1, col2 = st.columns([3, 1])  # Create two columns

        with col1:
            emergency_contact = st.text_input("Enter your emergency contact number", max_chars=10, help="Enter the number without +91")

        with col2:
            if st.button("Send Emergency Alert"):
                if emergency_contact:
                    send_emergency_message(emergency_contact, lat, lng)
                else:
                    st.warning("Please enter a valid emergency contact number.")

        # Nearby places search options
        st.subheader("Find Nearby Places")
        place_type = st.selectbox("Select Type:", ("Police Station", "Bus Stop"))

        # Button to search for nearby places
        if st.button("Search Nearby"):
            nearby_places = find_nearby_places(lat, lng, place_type)

            # Display nearby places
            if nearby_places:
                st.success(f"Found {len(nearby_places)} nearby {place_type.lower()}(s):")
                for place in nearby_places:
                    st.write(f"{place['name']}")
            else:
                st.warning("No nearby places found.")

        # Display map
        if lat and lng:
            st.write(f"Location: **{location_name}**")
            m = folium.Map(location=[lat, lng], zoom_start=12)

            # User's location marker
            folium.Marker(location=[lat, lng], popup=f"Your Location: {location_name}", icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)

            # Add incident markers from Firebase
            incident_data = fetch_incidents()
            for incident in incident_data:
                folium.Marker(location=[incident['latitude'], incident['longitude']],
                              popup=f"Incident: {incident['description']}<br>Location: {incident['location_name']}",
                              icon=folium.Icon(color='red', icon='exclamation-sign')).add_to(m)

            # Add markers for nearby places if searched
            if 'nearby_places' in locals() and nearby_places:
                for place in nearby_places:
                    folium.Marker(location=[place['latitude'], place['longitude']],
                                  popup=f"{place_type.capitalize()}: {place['name']}",
                                  icon=folium.Icon(color='green', icon='info-sign')).add_to(m)

            # Display the map
            folium_static(m)

        # Reporting Section
        st.subheader("Report an Incident")
        
        # Input for reporting location and description
        report_location = st.text_input("Enter Location for Incident (leave blank for current location):", value=location_name)
        description = st.text_area("Incident Description", placeholder="Describe what happened...")
        
        # Handle reporting incident
        if st.button("Submit Incident"):
            if description:
                # Use provided location or current location if empty
                if report_location:
                    reported_lat, reported_lng, reported_location_name = search_location(report_location)
                else:
                    reported_lat, reported_lng = lat, lng
                    reported_location_name = location_name
                
                if reported_lat is not None and reported_lng is not None:
                    report_incident(reported_location_name, reported_lat, reported_lng, description)
                    st.success("Incident reported successfully!")

                    # Add a marker for the reported incident location on the map
                    m.add_child(folium.Marker(location=[reported_lat, reported_lng],
                                               popup=f"Reported Incident: {description}<br>Location: {reported_location_name}",
                                               icon=folium.Icon(color='orange', icon='info-sign')))
                    folium_static(m)
                else:
                    st.error("Failed to find the reported location. Please check the location name.")
            else:
                st.error("Please provide a description of the incident.")
    else:
        st.warning("Unable to get your location. Please make sure you've granted location access.")

# Forum Tab
with tab2:
    st.header("Forum")

    # Input for forum message
    username = st.text_input("Enter your name (or leave blank for anonymous):")
    forum_message = st.text_area("Share your experience or message:")
    
    # Handle posting message
    if st.button("Post Message"):
        if forum_message:
            post_message(username if username else "Anonymous", forum_message)
            st.success("Message posted successfully!")
        else:
            st.error("Please enter a message to post.")

    # Display forum messages
    st.subheader("Forum Messages")
    forum_messages = fetch_forum_messages()
    
    if forum_messages:
        for msg in forum_messages:
            st.write(f"**{msg['username']}**: {msg['message']}")
            st.write(f"*Posted on: {msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}*")
            st.markdown("---")
    else:
        st.write("No messages yet. Be the first to share!")
