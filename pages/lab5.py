import json
import streamlit as st
import requests
from openai import OpenAI


def get_current_weather(location, api_key, units='imperial'):
    """Fetch current weather for a given location from OpenWeatherMap."""
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

    return {
        'location': location,
        'temperature': round(main.get('temp', 0), 2),
        'feels_like': round(main.get('feels_like', 0), 2),
        'temp_min': round(main.get('temp_min', 0), 2),
        'temp_max': round(main.get('temp_max', 0), 2),
        'humidity': round(main.get('humidity', 0), 2),
        'wind_speed': round(wind.get('speed', 0), 2),
        'description': data.get('weather', [{}])[0].get('description', ''),
    }


def main():
    st.title('Lab 5 — What to Wear Bot')
    st.write('Enter a city and the assistant will fetch the weather and suggest appropriate clothing and outdoor activities.')

    location = st.text_input('Location (City, ST, Country)', value='Syracuse, NY, US')
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

    if st.button('Get Advice'):
        if not openai_api_key:
            st.error('OpenAI API key not found in secrets (OPENAI_API_KEY).')
            return
        if not openweather_api_key:
            st.error('OpenWeatherMap API key not found in secrets (openweather.api_key).')
            return

        client = OpenAI(api_key=openai_api_key)

        system_prompt = (
            "You are a weather-aware assistant. When appropriate, call the "
            "tool `get_current_weather` to retrieve current weather for a location. "
            "If no location is provided, default to 'Syracuse, NY'. "
            "After obtaining weather, provide clothing suggestions and outdoor activity advice."
        )

        user_prompt = f"What should I wear today and what outdoor activities are appropriate for {location}?"

        weather_tool = {
            "name": "get_current_weather",
            "description": "Get current weather for a location. Returns temperature, feels_like, temp_min, temp_max, humidity, wind_speed, and description.",
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

        with st.spinner('Asking assistant...'):
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    functions=[weather_tool],
                    function_call="auto",
                )
            except Exception as e:
                st.error(f'Error calling OpenAI: {e}')
                return

            message = completion.choices[0].message

            func_call = getattr(message, "function_call", None)

            if func_call:
                try:
                    args = json.loads(func_call.arguments or "{}")
                except Exception:
                    args = {}

                tool_location = args.get("location") or location or "Syracuse, NY"
                tool_units = args.get("units") or units

                try:
                    weather = get_current_weather(tool_location, openweather_api_key, units=tool_units)
                except Exception as e:
                    st.error(f'Error fetching weather: {e}')
                    return

                # Send tool result back to the model
                messages.append(message)
                messages.append({
                    "role": "function",
                    "name": "get_current_weather",
                    "content": json.dumps(weather),
                })

                try:
                    followup = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                    )
                    final_response = followup.choices[0].message.content or ""
                except Exception as e:
                    st.error(f'Error generating response: {e}')
                    return
            else:
                final_response = message.content or ""

        st.subheader('Assistant Response')
        st.write(final_response)


if __name__ == '__main__':
    main()