import streamlit as st
import requests


def get_current_weather(location, api_key, units='imperial'):
    """Fetch current weather for a given location from OpenWeatherMap.
    location: string like 'Syracuse, NY, US'
    returns: dict with temperature, description, humidity, wind, and raw data
    """
    url = (
        f'https://api.openweathermap.org/data/2.5/weather'
        f'?q={location}&appid={api_key}&units={units}'
    )
    response = requests.get(url, timeout=10)
    if response.status_code == 401:
        raise Exception('Authentication failed: Invalid API key (401 Unauthorized)')
    if response.status_code == 404:
        error_message = response.json().get('message')
        raise Exception(f'404 error: {error_message}')
    response.raise_for_status()
    data = response.json()
    main = data.get('main', {})

    temp = main.get('temp')
    feels_like = main.get('feels_like')
    temp_min = main.get('temp_min')
    temp_max = main.get('temp_max')
    humidity = main.get('humidity')

    return {'location': location,
        'temperature': round(temp, 2),
        'feels_like': round(feels_like, 2),
        'temp_min': round(temp_min, 2),
        'temp_max': round(temp_max, 2),
        'humidity': round(humidity, 2)
    }


def clothing_suggestion(temp_f):
    suggestions = []
    if temp_f is None:
        return ['No temperature data available']
    if temp_f <= 32:
        suggestions.append('Heavy coat, thermal layers')
    elif temp_f <= 50:
        suggestions.append('Jacket and layers')
    elif temp_f <= 65:
        suggestions.append('Long sleeve shirt and light jacket')
    elif temp_f <= 75:
        suggestions.append('Light layers')
    else:
        suggestions.append('Shorts, breathable fabrics, hat, and sunscreen')
    return suggestions


def activity_advice(weather):
    temp = weather.get('temperature')
    humidity = weather.get('humidity') or 0
    advice = []
    if temp is not None:
        if temp < 20:
            advice.append('Very cold — avoid long outdoor exertion.')
        elif 50 <= temp <= 75 and humidity < 80:
            advice.append('Good conditions for walking, jogging, or a picnic.')
        elif temp > 75:
            advice.append('Hot — schedule strenuous activity for morning/evening.')
    if humidity and humidity > 90:
        advice.append('High humidity — it may feel muggy; consider indoor alternatives.')
    if not advice:
        advice.append('No specific cautions — enjoy your outdoor plans.')
    return advice


def main():
    st.title('Lab 5 — Weather & Clothing Suggestions')
    st.write('Retrieve current weather and get clothing/activity advice.')

    default_location = 'Syracuse, NY, US'
    location = st.text_input('Location (City, ST, Country)', value=default_location)

    # Attempt to read API key from Streamlit secrets
    api_key = None
    try:
        api_key = st.secrets['openweather']['api_key']
    except Exception:
        api_key = None

    if not api_key:
        st.error('OpenWeatherMap API key not found')
        st.stop()

    units = st.selectbox('Units', options=['imperial', 'metric'], index=0)

    if st.button('Get Weather'):
        with st.spinner('Fetching weather...'):
            try:
                weather = get_current_weather(location, api_key, units=units)
            except Exception as e:
                st.error(f'Error fetching weather: {e}')
                return

        st.subheader(f"Current weather for {weather.get('location')}")
        cols = st.columns(3)
        cols[0].metric('Temp', f"{weather.get('temperature')} °{'F' if units=='imperial' else 'C'}", delta=None)
        cols[1].metric('Feels like', f"{weather.get('feels_like')} °{'F' if units=='imperial' else 'C'}")
        cols[2].metric('Humidity', f"{weather.get('humidity')} %")


        st.markdown('**Clothing suggestions**')
        for s in clothing_suggestion(weather.get('temperature')):
            st.write('- ' + s)

        st.markdown('**Activity advice**')
        for a in activity_advice(weather):
            st.write('- ' + a)


if __name__ == '__main__':
    main()
