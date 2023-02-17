import datetime as dt
import json

import requests
from flask import Flask, jsonify, request

# create your API token, and set it up in Postman collection as part of the Body section
API_TOKEN = "iamsecure"

app = Flask(__name__)


def get_city_coords(country: str, city: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {'name': city}

    response = requests.request("GET", url, params=params)
    status = response.status_code

    json_data = response.json()
    
    if json_data.get('error') == True:
        raise InvalidUsage(response.get('reason') or 'Unknown weather api errror', status_code=400)

    results = json_data.get("results")

    if results is None:
        raise InvalidUsage("Location not found", status_code=404)

    matching_cities = list(filter(lambda city: (city.get('country').lower() == country.lower()), results))
    
    if len(matching_cities) == 0:
        raise InvalidUsage("Location not found", status_code=404)
        
    matching_city = matching_cities[0]

    return (matching_city.get('latitude'), matching_city.get('longitude'))

def assign_dict_props(props, src: dict, dest: dict): 
    for prop_name in props:
        dest[prop_name] = src.get(prop_name)
    

def get_weather(latitude: float, longitude: float, start_date: float, end_date: float):
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': start_date,
        'end_date': end_date,
        'models': 'best_match',
        'daily': [
            'temperature_2m_max',
            'temperature_2m_min',
            'temperature_2m_mean',
            'precipitation_sum',
            'windspeed_10m_max'
        ],
        'hourly': [
           'relativehumidity_2m',
            'temperature_2m',
            'windspeed_10m'
        ],
        "timezone": "GMT"
    }

    response = requests.request("GET", url, params=params).json()
    
    if response.get('error') == True:
        raise InvalidUsage(response.get('reason') or 'Unknown weather api errror', status_code=400)
    
    result = {}
    
    assign_dict_props(['daily', 'daily_units', 'hourly', 'hourly_units'], response, result)
    
    return result
    

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/")
def home_page():
    return "<p><h2>KMA L2: Python Saas.</h2></p>"


def validate_required(field_names, obj: dict):
    for f_name in field_names: 
        val = obj.get(f_name) 
        if val is None or val == '':
            raise InvalidUsage(f"{f_name} is required", status_code=400)
           
        
@app.route(
    "/content/api/v1/integration/weather",
    methods=["POST"],
)            
def weather_endpoint():
    json_data = request.get_json()

    if json_data.get("token") is None:
        raise InvalidUsage("token is required", status_code=400)

    token = json_data.get("token")

    if token != API_TOKEN:
        raise InvalidUsage("wrong API token", status_code=403)
        
    validate_required(["start_date", "end_date", "location", "requester_name"], json_data)
        
    start_date = json_data.get("start_date")
    end_date = json_data.get("end_date")
    requester_name = json_data.get('requester_name')
    location = json_data.get("location")

    if ":" not in location: 
        raise InvalidUsage("Please provide location in format: 'Country:City'", status_code=400)

    country, city = location.split(':', 1)

    latitude, longitude = get_city_coords(country, city)

    weather_result = get_weather(latitude, longitude, start_date, end_date)
    
    return {
        'requester_name': requester_name,
        'start_date': start_date,
        'end_date': end_date,
        'weather': weather_result
    }
