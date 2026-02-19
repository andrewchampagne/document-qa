import json
import streamlit as st
import requests
from openai import OpenAI


def get_current_weather(location, api_key, units='imperial'):
    """Fetch current weather for a given location from OpenWeatherMap.
    location: string like 'Syracuse, NY, US' (or 'Syracuse, NY')
    returns: dict with temperature, feels_like, temp_min, temp_max, humidity, wind_speed, and raw data
    """
    if not location:
        location = 'Syracuse, NY'
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
    wind = data.get('wind', {})

    temp = main.get('temp')
    feels_like = main.get('feels_like')
    temp_min = main.get('temp_min')
    temp_max = main.get('temp_max')
    humidity = main.get('humidity')
    wind_speed = wind.get('speed')

    return {
        'location': location,
        'temperature': round(temp, 2) if temp is not None else None,
        'feels_like': round(feels_like, 2) if feels_like is not None else None,
        'temp_min': round(temp_min, 2) if temp_min is not None else None,
        'temp_max': round(temp_max, 2) if temp_max is not None else None,
        'humidity': round(humidity, 2) if humidity is not None else None,
        'wind_speed': round(wind_speed, 2) if wind_speed is not None else None,
        'raw': data,
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
    st.title('Lab 5 — Weather & Clothing Suggestions with OpenAI')
    st.write('Enter a city and either fetch the weather directly or ask the assistant for clothing/activity advice. The assistant may call a weather tool when needed.')

    default_location = 'Syracuse, NY, US'
    location = st.text_input('Location (City, ST, Country)', value=default_location)
    units = st.selectbox('Units', options=['imperial', 'metric'], index=0)

    # Read API keys from secrets
    try:
        openai_api_key = st.secrets['OPENAI_API_KEY']
    except Exception:
        openai_api_key = None

    try:
        openweather_api_key = st.secrets['openweather']['api_key']
    except Exception:
        openweather_api_key = None

    # Direct weather fetch UI
    st.divider()
    st.subheader('Direct weather lookup')
    if st.button('Get Weather'):
        if not openweather_api_key:
            st.error('OpenWeatherMap API key not found in secrets (openweather.api_key).')
        else:
            with st.spinner('Fetching weather...'):
                try:
                    weather = get_current_weather(location, openweather_api_key, units=units)
                except Exception as e:
                    st.error(f'Error fetching weather: {e}')
                    return

            st.subheader(f"Current weather for {weather.get('location')}")
            cols = st.columns(3)
            cols[0].metric('Temp', f"{weather.get('temperature')} °{'F' if units=='imperial' else 'C'}")
            cols[1].metric('Feels like', f"{weather.get('feels_like')} °{'F' if units=='imperial' else 'C'}")
            cols[2].metric('Humidity', f"{weather.get('humidity')} %")

            st.markdown('**Clothing suggestions**')
            for s in clothing_suggestion(weather.get('temperature')):
                st.write('- ' + s)

            st.markdown('**Activity advice**')
            for a in activity_advice(weather):
                st.write('- ' + a)

    # OpenAI-assisted advice (tool-calling)
    st.divider()
    st.subheader('Ask assistant (OpenAI) for clothing & activity advice')

    if st.button('Ask Bot for Advice'):
        if not openai_api_key:
            st.error('OpenAI API key not found in secrets (OPENAI_API_KEY).')
            return

        client = OpenAI(api_key=openai_api_key)

        system_prompt = (
            "You are a weather-aware assistant. When appropriate, you may call the "
            "tool `get_current_weather` to retrieve current weather for a location. If you request weather but no location is provided, default to 'Syracuse, NY'. "
            "After obtaining weather, provide clothing suggestions and outdoor activity advice."
        )

        user_prompt = f"Provide clothing suggestions and outdoor activities appropriate for the user's location: {location}"

        weather_tool = {
            "name": "get_current_weather",
            "description": "Get current weather for a location. Returns temperature, feels_like, temp_min, temp_max, humidity, and wind_speed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Location as City, ST, Country"},
                    "units": {"type": "string", "enum": ["imperial", "metric"], "description": "Units for temperature"},
                },
                "required": [],
            },
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            completion = client.chat.completions.create(
                model="gpt-5-mini",
                messages=messages,
                functions=[weather_tool],
                function_call="auto",
            )
        except Exception as e:
            st.error(f'Error calling OpenAI: {e}')
            return

        message = completion.choices[0].message

        # Check if model requested the tool
        func_call = None
        if isinstance(message, dict):
            func_call = message.get("function_call")
        else:
            func_call = getattr(message, "function_call", None)

        final_response = None
        if func_call:
            # Parse arguments from the function call
            args_str = func_call.get("arguments") if isinstance(func_call, dict) else getattr(func_call, "arguments", None)
            try:
                args = json.loads(args_str or "{}")
            except Exception:
                args = {}

            tool_location = args.get("location") or location or "Syracuse, NY"
            tool_units = args.get("units") or units

            if not openweather_api_key:
                st.error('OpenWeatherMap API key not found in secrets (openweather.api_key). Tool cannot be invoked.')
                return

            try:
                weather = get_current_weather(tool_location, openweather_api_key, units=tool_units)
            except Exception as e:
                st.error(f'Error fetching weather from OpenWeatherMap: {e}')
                return

            # Provide the function result back to the model. Some models/platforms
            # don't accept messages with role 'function', so return the tool
            # output as an assistant message instead.
            messages.append({"role": "assistant", "content": json.dumps({"tool": "get_current_weather", "result": weather})})

            try:
                followup = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=messages,
                )
                final_response = followup.choices[0].message.content or ""
            except Exception as e:
                st.error(f'Error generating final assistant response: {e}')
                return
        else:
            final_response = message.content or ""

        st.subheader('Assistant response')
        st.write(final_response)


if __name__ == '__main__':
    main()
