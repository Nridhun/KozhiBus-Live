
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import simulation
app = FastAPI(title="KozhiBus Live API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
         "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Project and dataset paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"

# Load our datasets
trips_df, routes_df, times_df = simulation.load_datasets()

# Load trained ML components
ml_model, ml_preprocessor, ml_features = (
    simulation.load_ml_components()
)

@app.get("/")
def home():
    return {
        "message": "Welcome to KozhiBus Live API",
        "status": "Running"
    }


@app.get("/api/data-check")
def data_check():
    return {
        "trip_rows": len(trips_df),
        "route_rows": len(routes_df),
        "time_rows": len(times_df),
        "message": "All three datasets loaded successfully"
    }

@app.get("/api/locations")
def get_locations():

    locations = pd.concat([
        routes_df["Stop_Name"],
        routes_df["Starting_Stop"],
        routes_df["Ending_Stop"]
    ])

    locations = sorted(
        locations.dropna().astype(str).unique().tolist()
    )

    return {
        "total_locations": len(locations),
        "locations": locations
    }

@app.get("/api/corridors")
def get_top_corridors():

    # Group trips by starting and ending stops
    corridor_stats = (
        trips_df.groupby(
            ["Starting_Stop", "Ending_Stop"]
        )
        .agg(
            total_trips=("Trip_ID", "nunique"),
            average_distance_km=("Distance_km", "mean"),
            average_duration_min=("Scheduled_Duration_Min", "mean"),
            active_days=("Journey_Date", "nunique")
        )
        .reset_index()
    )

    # Calculate average trips per operating day
    corridor_stats["average_trips_per_day"] = (
        corridor_stats["total_trips"] /
        corridor_stats["active_days"]
    )

    # Sort by highest number of trips
    top_corridors = (
        corridor_stats
        .sort_values("total_trips", ascending=False)
        .head(5)
    )

    # Convert results into JSON-friendly format
    corridors = []

    for _, row in top_corridors.iterrows():

        corridors.append({
            "origin": row["Starting_Stop"],
            "destination": row["Ending_Stop"],
            "total_trips": int(row["total_trips"]),
            "average_distance_km": round(
                float(row["average_distance_km"]), 1
            ),
            "average_duration_min": round(
                float(row["average_duration_min"]), 1
            ),
            "active_days": int(row["active_days"]),
            "average_trips_per_day": round(
                float(row["average_trips_per_day"]), 1
            )
        })

    return {
        "total_corridors": len(corridors),
        "corridors": corridors
    }


from datetime import datetime
from fastapi import HTTPException

@app.get("/api/buses")
def get_available_buses(
    origin: str,
    destination: str,
    date: str,
    start_time: int = 300,
    end_time: int = 420
):
    try:
        # Convert selected date
        journey_date = pd.to_datetime(
            date,
            format="%Y-%m-%d",
            errors="coerce"
        )

        if pd.isna(journey_date):
            raise HTTPException(
                status_code=400,
                detail="Invalid date. Use YYYY-MM-DD."
            )

        if start_time < 0 or end_time > 1439 or start_time >= end_time:
            raise HTTPException(
                status_code=400,
                detail="Invalid departure time range."
            )

        if simulation.normalise_text(origin) == simulation.normalise_text(destination):
            raise HTTPException(
                status_code=400,
                detail="Origin and destination cannot be the same."
            )

        # Generate temporary data for the selected date
        temporary_table1, temporary_table3, template_date = (
            simulation.generate_temporary_daily_data(
                trips_df,
                times_df,
                journey_date.normalize()
            )
        )

        # Search available journeys
        results = simulation.search_available_buses(
            temporary_table1,
            temporary_table3,
            origin,
            destination,
            journey_date,
            start_time,
            end_time
        )

        if results.empty:
            return {
                "buses": [],
                "total": 0,
                "data_type": "TEMPORARY_SIMULATION",
                "message": "No matching buses found."
            }

        buses = []

        for _, result in results.head(20).iterrows():

            journey = temporary_table3[
                temporary_table3["Journey_ID"] == result["Journey_ID"]
            ].sort_values("Stop_Sequence").copy()

            origin_rows = journey[
                journey["Stop_Sequence"] == result["From_Sequence"]
            ]

            if origin_rows.empty:
                continue

            origin_row = origin_rows.iloc[0]

            next_rows = journey[
                journey["Stop_Sequence"] > result["From_Sequence"]
            ].sort_values("Stop_Sequence")

            next_stop = (
                next_rows.iloc[0]["Stop_Name"]
                if not next_rows.empty
                else "Destination"
            )

            # Run the trained ML model
            predicted_remaining_delay = simulation.predict_delay(
                origin_row,
                next_stop,
                journey_date,
                ml_model,
                ml_preprocessor,
                ml_features
            )

            # Scheduled arrival at the passenger's selected destination
            scheduled_arrival = result["Scheduled_Arrival"]

            scheduled_arrival_min = simulation.time_to_minutes(
                scheduled_arrival
            )

            # Calculate ML-predicted arrival at the passenger's selected destination
            scheduled_arrival = result["Scheduled_Arrival"]

            scheduled_arrival_min = simulation.time_to_minutes(
                scheduled_arrival
            )

            predicted_arrival = None

            if (
                    predicted_remaining_delay is not None
                    and scheduled_arrival_min is not None
            ):
                predicted_arrival_min = (
                        scheduled_arrival_min + predicted_remaining_delay
                )

                predicted_arrival = (
                    f"{int(predicted_arrival_min // 60) % 24:02d}:"
                    f"{int(predicted_arrival_min % 60):02d}"
                )
            def safe_value(value):
                if pd.isna(value):
                    return None
                if hasattr(value, "item"):
                    return value.item()
                return value

            # Get only the stops between the passenger's selected origin and destination
            selected_stops = journey[
                (journey["Stop_Sequence"] >= result["From_Sequence"])
                & (journey["Stop_Sequence"] <= result["To_Sequence"])
                ].sort_values("Stop_Sequence")

            stops = []

            stop_count = len(selected_stops)

            for index, (_, stop) in enumerate(selected_stops.iterrows()):

                scheduled_time = str(stop["Scheduled_Arrival"])

                # Calculate ML-predicted arrival time for this stop
                scheduled_minutes = simulation.time_to_minutes(
                    scheduled_time
                )

                if (
                        predicted_remaining_delay is not None
                        and scheduled_minutes is not None
                ):
                    predicted_minutes = (
                            scheduled_minutes + predicted_remaining_delay
                    )

                    predicted_time = (
                        f"{int(predicted_minutes // 60) % 24:02d}:"
                        f"{int(predicted_minutes % 60):02d}"
                    )
                else:
                    predicted_time = scheduled_time

                # Coordinates are schematic positions for the existing SVG animation,
                # NOT real GPS coordinates.
                if stop_count > 1:
                    x = 100 + (index / (stop_count - 1)) * 800
                else:
                    x = 500

                y = 350 + 100 * ((-1) ** index) * (index / max(stop_count, 1))

                stops.append({
                    "id": str(stop["Stop_Sequence"]),
                    "name": str(stop["Stop_Name"]),
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "scheduledTime": scheduled_time,
                    "predictedTime": predicted_time,
                    "distanceKm": 0,
                    "status": "current" if index == 0 else "upcoming"
                })
            buses.append({
                "journey_id": str(result["Journey_ID"]),
                "trip_id": str(result["Trip_ID"]),
                "bus_id": str(result["Bus_ID"]),
                "bus_type": str(result["Bus_Type"]),
                "route_id": str(result["Route_ID"]),
                "origin": str(result["From_Stop"]),
                "destination": str(result["To_Stop"]),
                "departure_time": str(result["Scheduled_Departure"]),
                "scheduled_arrival": str(scheduled_arrival),
                "predicted_arrival": predicted_arrival,
                "distance_km": safe_value(result["Distance_km"]),
                "scheduled_duration_min": safe_value(
                    result["Scheduled_Duration_Min"]
                ),
                "traffic_level": safe_value(result["Traffic_Level"]),
                "weather_condition": safe_value(result["Weather_Condition"]),
                "predicted_remaining_delay_min": (
                    round(predicted_remaining_delay, 2)
                    if predicted_remaining_delay is not None
                    else None
                ),

                "prediction_status": (
                    "ML_PREDICTED"
                    if predicted_remaining_delay is not None
                    else "PREDICTION_UNAVAILABLE"
                ),
                "data_type": "TEMPORARY_SIMULATION",
                             "stops": stops
            })

        return {
            "buses": buses,
            "total": len(buses),
            "requested_date": journey_date.strftime("%Y-%m-%d"),
            "historical_template_date": template_date.strftime("%Y-%m-%d"),
            "data_type": "TEMPORARY_SIMULATION"
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
