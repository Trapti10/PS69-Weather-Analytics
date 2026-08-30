import cdsapi

dataset = "reanalysis-era5-single-levels-timeseries"
request = {
    "variable": [
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "10m_wind_gust_since_previous_post_processing",
        "2m_dewpoint_temperature",
        "2m_temperature",
        "mean_sea_level_pressure",
        "total_precipitation"
    ],
"location": {
    "longitude": 79.95,
    "latitude": 23.18
},
    "date": ["2024-01-01/2025-12-31"],
    "data_format": "csv"
}

client = cdsapi.Client()

result = client.retrieve(dataset, request)

result.download("jabalpur_weather_2024_2025.csv")