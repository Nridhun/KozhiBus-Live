"""Bus search and journey simulation for the Kozhikode bus prediction project.

Uses the three project CSV files without modifying the original files.
Only today and tomorrow can be searched. Since the supplied records end in 2025,
the program uses the latest historical date with the same weekday as a schedule
template. Results are simulated, not confirmation of real-world bus availability.
Table 3 supplies stop order and stop-level scheduled timings.
"""

from pathlib import Path
import sys
from datetime import date, timedelta, datetime

import now
import pandas as pd
import joblib



# ============================================================
# 1. PROJECT PATHS AND SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"
MODEL_DIR = BASE_DIR / "Models"

TABLE1_FILE = DATA_DIR / "BusTime_Tb1.csv"
TABLE2_FILE = DATA_DIR / "RouteInfo_Tb2.csv"
TABLE3_FILE = DATA_DIR / "TimeInfo_Tb3.csv"

MODEL_FILE = MODEL_DIR / "live_delay_model.pkl"
PREPROCESSOR_FILE = MODEL_DIR / "live_delay_preprocessor.pkl"
FEATURES_FILE = MODEL_DIR / "live_delay_features.pkl"

SERVICE_STOP_COLUMN = {
    "Ordinary": "Ordinary_Stop",
    "Limited Stop": "Limited_Stop_Stop",
    "Superfast": "Superfast_Stop",
    "Fast Passenger": "Fast_Passenger_Stop",
}


# ============================================================
# 2. GENERAL HELPER FUNCTIONS
# ============================================================

def normalise_text(value):
    """Standardise text for comparisons without changing source data."""
    if pd.isna(value):
        return ""
    return str(value).strip().casefold()


def time_to_minutes(value):
    """Convert HH:MM to minutes after midnight."""
    if pd.isna(value):
        return None

    value = str(value).strip()
    parsed = pd.to_datetime(value, format="%H:%M", errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.hour * 60 + parsed.minute


def minutes_to_time(minutes):
    """Convert minutes after midnight to a readable 24-hour time."""
    if minutes is None or pd.isna(minutes):
        return "N/A"

    minutes = int(round(minutes)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
def get_bus_position(journey):
    """
    Estimate the bus position using the computer's real-time clock
    and the journey's scheduled stop timings.
    """

    journey = journey.sort_values("Stop_Sequence").reset_index(drop=True)

    # Get the journey date.
    journey_date = journey["_Journey_Date"].iloc[0].date()

    # Get the computer's current local date and time.
    now = datetime.now()

    # If the journey is scheduled for another date, compare against
    # that journey's date rather than today's date.
    current_time = now

    if now.date() != journey_date:
        current_time = datetime.combine(
            journey_date,
            now.time()
        )

    stop_times = []

    # Build absolute scheduled timestamps for each stop.
    current_day = journey_date
    previous_minutes = None

    for _, stop in journey.iterrows():

        arrival_min = stop["_Scheduled_Arrival_Min"]
        departure_min = stop["_Scheduled_Departure_Min"]

        if pd.isna(arrival_min) or pd.isna(departure_min):
            continue

        arrival_min = int(arrival_min)
        departure_min = int(departure_min)

        # Handle a journey crossing midnight.
        if previous_minutes is not None and arrival_min < previous_minutes - 720:
            current_day += timedelta(days=1)

        arrival_time = datetime.combine(
            current_day,
            datetime.min.time()
        ) + timedelta(minutes=arrival_min)

        departure_day = current_day

        if departure_min < arrival_min - 720:
            departure_day += timedelta(days=1)

        departure_time = datetime.combine(
            departure_day,
            datetime.min.time()
        ) + timedelta(minutes=departure_min)

        stop_times.append({
            "stop": stop,
            "arrival": arrival_time,
            "departure": departure_time
        })

        previous_minutes = departure_min

    if not stop_times:
        return {"status": "Unknown"}

    # Check whether the bus has started.
    if current_time < stop_times[0]["departure"]:
        return {
            "status": "Not Started",
            "current_stop": None,
            "next_stop": stop_times[0]["stop"]["Stop_Name"]
        }

    # Check each stop.
    for i, item in enumerate(stop_times):

        # Bus is currently at this stop.
        if item["arrival"] <= current_time <= item["departure"]:
            next_stop = (
                stop_times[i + 1]["stop"]["Stop_Name"]
                if i + 1 < len(stop_times)
                else None
            )

            return {
                "status": "At Stop",
                "current_stop": item["stop"]["Stop_Name"],
                "next_stop": next_stop,
                "stop_sequence": int(item["stop"]["Stop_Sequence"])
            }

        # Bus has departed this stop and is travelling to the next.
        if i + 1 < len(stop_times):
            next_item = stop_times[i + 1]

            if item["departure"] < current_time < next_item["arrival"]:
                return {
                    "status": "Travelling",
                    "current_stop": item["stop"]["Stop_Name"],
                    "next_stop": next_item["stop"]["Stop_Name"],
                    "stop_sequence": int(item["stop"]["Stop_Sequence"])
                }

    # Check whether the journey is completed.
    if current_time > stop_times[-1]["arrival"]:
        return {
            "status": "Completed",
            "current_stop": stop_times[-1]["stop"]["Stop_Name"],
            "next_stop": None,
            "stop_sequence": int(stop_times[-1]["stop"]["Stop_Sequence"])
        }

    return {"status": "Unknown"}


def ask_date(prompt):
    """Accept only today's date or tomorrow's date (local computer date)."""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    print("\nYou can search only for:")
    print("Today   :", today.strftime("%d-%m-%Y"))
    print("Tomorrow:", tomorrow.strftime("%d-%m-%Y"))

    while True:
        value = input(prompt).strip()
        parsed = pd.to_datetime(value, format="%d-%m-%Y", errors="coerce")
        if pd.isna(parsed):
            print("Invalid date. Please use DD-MM-YYYY.")
            continue

        selected_date = parsed.date()
        if selected_date in (today, tomorrow):
            return pd.Timestamp(selected_date)

        print("Please select today or tomorrow only.")


def ask_time(prompt):
    """Read a time in HH:MM 24-hour format."""
    while True:
        value = input(prompt).strip()
        minutes = time_to_minutes(value)
        if minutes is not None:
            return minutes
        print("Invalid time. Please enter HH:MM, for example 09:30.")


# ============================================================
# 3. LOAD THE THREE DATASETS
# ============================================================

def load_datasets():
    required_files = [TABLE1_FILE, TABLE2_FILE, TABLE3_FILE]
    missing_files = [str(path) for path in required_files if not path.exists()]

    if missing_files:
        raise FileNotFoundError(
            "The following CSV file(s) were not found:\n" + "\n".join(missing_files)
            + "\n\nKeep the files inside the project's Data folder and use the filenames "
              "BusTime_Tb1.csv, RouteInfo_Tb2.csv and TimeInfo_Tb3.csv."
        )

    table1 = pd.read_csv(TABLE1_FILE)
    table2 = pd.read_csv(TABLE2_FILE)
    table3 = pd.read_csv(TABLE3_FILE)

    # Remove accidental spaces from column headings.
    for dataframe in (table1, table2, table3):
        dataframe.columns = dataframe.columns.str.strip()

    # Parse dates into temporary helper columns; original date columns remain intact.
    table1["_Journey_Date"] = pd.to_datetime(
        table1["Journey_Date"], format="%d-%m-%Y", errors="coerce"
    ).dt.normalize()
    table3["_Journey_Date"] = pd.to_datetime(
        table3["Date"], format="%d-%m-%Y", errors="coerce"
    ).dt.normalize()

    # Temporary normalised stop names and numeric scheduled times.
    table3["_Stop_Key"] = table3["Stop_Name"].map(normalise_text)
    table3["_Scheduled_Arrival_Min"] = table3["Scheduled_Arrival"].map(time_to_minutes)
    table3["_Scheduled_Departure_Min"] = table3["Scheduled_Departure"].map(time_to_minutes)

    return table1, table2, table3


# ============================================================
# 4. LOAD SAVED MACHINE-LEARNING COMPONENTS (OPTIONAL)
# ============================================================

def load_ml_components():
    """Load the trained model files if all three are available."""
    paths = [MODEL_FILE, PREPROCESSOR_FILE, FEATURES_FILE]

    if not all(path.exists() for path in paths):
        print("\nWARNING: ML model files were not all found.")
        print("Bus search and journey details will still work.")
        print("Predicted delay will be unavailable until the model files are present.")
        return None, None, None

    try:
        model = joblib.load(MODEL_FILE)
        preprocessor = joblib.load(PREPROCESSOR_FILE)
        features = joblib.load(FEATURES_FILE)
        print("\nSaved ML model components loaded successfully.")
        return model, preprocessor, list(features)
    except Exception as error:
        print(f"\nWARNING: Could not load ML components: {error}")
        return None, None, None


# ============================================================
# 5. DATASET INSPECTION AND VALIDATION
# ============================================================

def inspect_datasets(table1, table2, table3):
    print("\n" + "=" * 65)
    print("DATASET INFORMATION")
    print("=" * 65)

    for name, dataframe in [
        ("TABLE 1 - TRIP INFORMATION", table1),
        ("TABLE 2 - ROUTE INFORMATION", table2),
        ("TABLE 3 - STOP TIMING INFORMATION", table3),
    ]:
        print(f"\n{name}")
        print("Shape:", dataframe.shape)
        print("Missing values:", int(dataframe.isnull().sum().sum()))
        print("Duplicate complete rows:", int(dataframe.duplicated().sum()))
        print("Columns:", dataframe.columns.tolist())

    print("\nRELATIONSHIP VALIDATION")
    print("Table 1 unique Trip_ID:", table1["Trip_ID"].nunique())
    print("Table 3 unique Trip_ID:", table3["Trip_ID"].nunique())

    missing_trip_ids = set(table3["Trip_ID"].dropna()) - set(table1["Trip_ID"].dropna())
    print("Table 3 Trip_ID values missing from Table 1:", len(missing_trip_ids))

    merged = table3[["Trip_ID", "Route_ID"]].drop_duplicates().merge(
        table1[["Trip_ID", "Route_ID"]].drop_duplicates(),
        on="Trip_ID", how="left", suffixes=("_T3", "_T1")
    )
    route_mismatches = merged[
        merged["Route_ID_T1"].notna()
        & (merged["Route_ID_T3"] != merged["Route_ID_T1"])
    ]
    print("Trip/Route mismatches between Table 1 and Table 3:", len(route_mismatches))

    print("\nDATE COVERAGE")
    valid_dates = table3["_Journey_Date"].dropna()
    if not valid_dates.empty:
        print("First date:", valid_dates.min().strftime("%d-%m-%Y"))
        print("Last date:", valid_dates.max().strftime("%d-%m-%Y"))

    print("\nTABLE 2 STOP SEQUENCE CHECK")
    if "Stop_Sequence" in table2.columns:
        missing_sequence = int(table2["Stop_Sequence"].isna().sum())
        print("Missing Stop_Sequence values:", missing_sequence, "of", len(table2))
        print("Note: Table 3 Stop_Sequence will be used to order journey stops.")

    print("\nSERVICE STOPPING RULE VALIDATION")
    for bus_type, flag_column in SERVICE_STOP_COLUMN.items():
        if flag_column not in table2.columns:
            print(f"{bus_type}: column {flag_column} not found in Table 2")
            continue
        print(f"{bus_type}: Yes={(table2[flag_column] == 'Yes').sum()}, "
              f"No={(table2[flag_column] == 'No').sum()}, "
              f"Missing={table2[flag_column].isna().sum()}")

    print("\nNOTE: These datasets are labelled simulated in their Data_Type fields.")
    print("The application must not describe this historical dataset as live GPS data.")


# ============================================================
# 6. VALIDATE TABLE 3 STOPPING PATTERNS AGAINST TABLE 2
# ============================================================

def validate_service_stops(table2, table3):
    needed = ["Route_ID", "Stop_Name"] + list(SERVICE_STOP_COLUMN.values())
    route_stops = table2[needed].drop_duplicates(["Route_ID", "Stop_Name"])

    checked = table3[["Route_ID", "Stop_Name", "Bus_Type"]].drop_duplicates().merge(
        route_stops, on=["Route_ID", "Stop_Name"], how="left"
    )

    print("\nTABLE 3 VS TABLE 2 SERVICE STOP CHECK")
    for bus_type, flag_column in SERVICE_STOP_COLUMN.items():
        rows = checked[checked["Bus_Type"] == bus_type]
        invalid = rows[rows[flag_column] != "Yes"]
        print(f"{bus_type}: {len(invalid)} stop/service mismatches")


# ============================================================
# 7. GENERATE TEMPORARY DATA FOR TODAY OR TOMORROW
# ============================================================

def generate_temporary_daily_data(table1, table3, requested_date):
    """Create an in-memory copy of one historical weekday as a temporary day.

    The original DataFrames and CSV files are never changed. No generated
    records are written to disk. The copied date columns are changed to the
    requested date only for this running application session.
    """
    target_weekday = requested_date.dayofweek

    dates1 = pd.to_datetime(
        table1["Journey_Date"], format="%d-%m-%Y", errors="coerce"
    ).dt.normalize()
    dates3 = pd.to_datetime(
        table3["Date"], format="%d-%m-%Y", errors="coerce"
    ).dt.normalize()

    # Use only dates represented in BOTH Table 1 and Table 3.
    common_dates = set(dates1.dropna().unique()).intersection(
        dates3.dropna().unique()
    )
    weekday_dates = [
        pd.Timestamp(value) for value in common_dates
        if pd.Timestamp(value).dayofweek == target_weekday
    ]

    if not weekday_dates:
        raise ValueError(
            "No matching historical weekday exists in both Table 1 and Table 3."
        )

    template_date = max(weekday_dates)

    # Copy only; never modify the original historical DataFrames.
    temporary_table1 = table1.loc[dates1 == template_date].copy()
    temporary_table3 = table3.loc[dates3 == template_date].copy()

    if temporary_table1.empty or temporary_table3.empty:
        raise ValueError("The selected historical template contains no records.")

    # Change dates in memory to the user's selected date.
    temporary_table1["Journey_Date"] = requested_date.strftime("%d-%m-%Y")
    temporary_table3["Date"] = requested_date.strftime("%d-%m-%Y")

    # Clearly label these as temporary synthetic records when the field exists.
    if "Data_Type" in temporary_table1.columns:
        temporary_table1["Data_Type"] = "TEMPORARY_SIMULATION"
    if "Data_Type" in temporary_table3.columns:
        temporary_table3["Data_Type"] = "TEMPORARY_SIMULATION"

    # Rebuild helper columns after copying and changing the date.
    temporary_table1["_Journey_Date"] = requested_date.normalize()
    temporary_table3["_Journey_Date"] = requested_date.normalize()
    temporary_table3["_Stop_Key"] = temporary_table3["Stop_Name"].map(normalise_text)
    temporary_table3["_Scheduled_Arrival_Min"] = temporary_table3["Scheduled_Arrival"].map(time_to_minutes)
    temporary_table3["_Scheduled_Departure_Min"] = temporary_table3["Scheduled_Departure"].map(time_to_minutes)

    print("\nTEMPORARY DAILY DATA GENERATED IN MEMORY")
    print("Requested date:", requested_date.strftime("%d-%m-%Y"))
    print("Historical template date:", template_date.strftime("%d-%m-%Y"))
    print("Temporary Table 1 records:", len(temporary_table1))
    print("Temporary Table 3 records:", len(temporary_table3))
    print("No CSV files were created or modified.")

    return temporary_table1, temporary_table3, template_date


# ============================================================
# 8. SEARCH BUSES USING USER INPUT
# ============================================================

def search_available_buses(
    table1, table3, from_stop, to_stop, journey_date, start_time, end_time
):
    """Search the temporary in-memory daily data for matching journeys."""
    from_key = normalise_text(from_stop)
    to_key = normalise_text(to_stop)

    date_rows = table3[table3["_Journey_Date"] == journey_date.normalize()].copy()
    matches = []

    for journey_id, journey in date_rows.groupby("Journey_ID", sort=False):
        journey = journey.sort_values("Stop_Sequence")
        journey["_Stop_Key"] = journey["Stop_Name"].map(normalise_text)

        origin_rows = journey[journey["_Stop_Key"] == from_key]
        destination_rows = journey[journey["_Stop_Key"] == to_key]

        if origin_rows.empty or destination_rows.empty:
            continue

        origin = origin_rows.sort_values("Stop_Sequence").iloc[0]
        destination_rows = destination_rows[
            destination_rows["Stop_Sequence"] > origin["Stop_Sequence"]
        ]
        if destination_rows.empty:
            continue

        destination = destination_rows.sort_values("Stop_Sequence").iloc[0]
        departure_min = origin["_Scheduled_Departure_Min"]
        if departure_min is None or pd.isna(departure_min):
            continue

        # The user's time window applies to departure from the selected From stop.
        if not (start_time <= departure_min <= end_time):
            continue

        matches.append({
            "Journey_ID": journey_id,
            "Requested_Journey_Date": journey_date.strftime("%d-%m-%Y"),
            "Trip_ID": origin["Trip_ID"],
            "Bus_ID": origin["Bus_ID"],
            "Bus_Type": origin["Bus_Type"],
            "Route_ID": origin["Route_ID"],
            "From_Stop": origin["Stop_Name"],
            "To_Stop": destination["Stop_Name"],
            "Scheduled_Departure": origin["Scheduled_Departure"],
            "Scheduled_Arrival": destination["Scheduled_Arrival"],
            "From_Sequence": int(origin["Stop_Sequence"]),
            "To_Sequence": int(destination["Stop_Sequence"]),
        })

    if not matches:
        return pd.DataFrame()

    results = pd.DataFrame(matches)
    trip_details = table1.drop_duplicates("Trip_ID")[[
        "Trip_ID", "Distance_km", "Scheduled_Duration_Min", "Weather_Condition",
        "Traffic_Level", "Festival_Eve", "Delay_Min"
    ]]
    results = results.merge(trip_details, on="Trip_ID", how="left")
    return results.sort_values(
        ["Scheduled_Departure", "Bus_ID"]
    ).reset_index(drop=True)


# ============================================================
# 8. DISPLAY AVAILABLE BUSES
# ============================================================

def display_bus_results(results):
    print("\n" + "=" * 90)
    print("AVAILABLE SCHEDULED BUSES")
    print("=" * 90)

    results = results.copy()
    results.insert(0, "Result_No", range(1, len(results) + 1))
    display_columns = [
        "Result_No", "Journey_ID", "Trip_ID", "Bus_ID", "Bus_Type", "Route_ID",
        "From_Stop", "To_Stop", "Scheduled_Departure", "Scheduled_Arrival",
        "Distance_km"
    ]
    print(results[display_columns].to_string(index=False))
    print("\nTotal matching buses:", len(results))


# ============================================================
# 9. PREDICT DELAY FOR THE SELECTED TRIP (IF MODEL AVAILABLE)
# ============================================================


def predict_delay(
    trip_row,
    next_stop,
    journey_date,
    model=None,
    preprocessor=None,
    features=None
):
    if model is None or preprocessor is None or not features:
        return None

    try:
        scheduled_arrival = time_to_minutes(
            trip_row["Scheduled_Arrival"]
        )

        actual_arrival = time_to_minutes(
            trip_row["Actual_Arrival"]
        )

        if scheduled_arrival is None or actual_arrival is None:
            return None

        current_delay = actual_arrival - scheduled_arrival

        journey_date = pd.to_datetime(journey_date)

        # Build the stop-level input used during model training
        input_values = {
            "Bus_Type": trip_row["Bus_Type"],
            "Route_ID": trip_row["Route_ID"],
            "Starting_Stop": trip_row["Starting_Stop"],
            "Ending_Stop": trip_row["Ending_Stop"],
            "Stop_Name": trip_row["Stop_Name"],
            "Next_Stop": next_stop,
            "Stop_Sequence": trip_row["Stop_Sequence"],
            "Day_of_Week": journey_date.dayofweek,
            "Month": journey_date.month,
            "Is_Weekend": int(journey_date.dayofweek >= 5),
            "Scheduled_Arrival_Min": scheduled_arrival,
            "Actual_Arrival_Min": actual_arrival,
            "Current_Delay_Min": current_delay
        }

        missing_features = [
            feature for feature in features
            if feature not in input_values
        ]

        if missing_features:
            print("Missing ML features:", missing_features)
            return None

        input_data = pd.DataFrame(
            [[input_values[feature] for feature in features]],
            columns=features
        )

        transformed_data = preprocessor.transform(input_data)

        prediction = float(
            model.predict(transformed_data)[0]
        )

        return max(0.0, prediction)

    except Exception as error:
        print(f"ML prediction error: {error}")
        return None



# ============================================================
# 10. DISPLAY SELECTED BUS JOURNEY
# ============================================================

def display_selected_journey(
    selected, table1, table3, model, preprocessor, features
):
    journey_id = selected["Journey_ID"]
    trip_id = selected["Trip_ID"]

    journey = table3[table3["Journey_ID"] == journey_id].copy()
    journey = journey.sort_values("Stop_Sequence")

    trip_matches = table1[table1["Trip_ID"] == trip_id]
    if trip_matches.empty:
        print("Trip details were not found in Table 1.")
        return

    trip = trip_matches.iloc[0]

    print("\n" + "=" * 75)
    print("SELECTED BUS - JOURNEY DETAILS")
    print("=" * 75)
    print("Journey ID:", journey_id)
    print("Trip ID:", trip_id)
    print("Bus ID:", trip["Bus_ID"])
    print("Bus Type:", trip["Bus_Type"])
    print("Route ID:", trip["Route_ID"])
    print("Requested Journey Date:", selected["Requested_Journey_Date"])
    print("From:", selected["From_Stop"])
    print("To:", selected["To_Stop"])
    print("Distance (route trip):", trip["Distance_km"], "km")

    # Keep only the passenger's selected section of the route.
    section = journey[
        (journey["Stop_Sequence"] >= selected["From_Sequence"])
        & (journey["Stop_Sequence"] <= selected["To_Sequence"])
    ].copy()

    predicted_delay = predict_delay(trip, model, preprocessor, features)

    print("\nSTOP-BY-STOP JOURNEY INFORMATION")
    output_rows = []
    for _, stop in section.iterrows():
        scheduled_arrival = stop["Scheduled_Arrival"]
        scheduled_departure = stop["Scheduled_Departure"]

        row = {
            "Sequence": int(stop["Stop_Sequence"]),
            "Stop": stop["Stop_Name"],
            "Scheduled Arrival": scheduled_arrival,
            "Scheduled Departure": scheduled_departure,
        }

        if predicted_delay is not None:
            arrival_min = stop["_Scheduled_Arrival_Min"]
            departure_min = stop["_Scheduled_Departure_Min"]
            row["Estimated Arrival"] = (
                minutes_to_time(arrival_min + predicted_delay)
                if arrival_min is not None and not pd.isna(arrival_min) else "N/A"
            )
            row["Estimated Departure"] = (
                minutes_to_time(departure_min + predicted_delay)
                if departure_min is not None and not pd.isna(departure_min) else "N/A"
            )

        output_rows.append(row)

    print(pd.DataFrame(output_rows).to_string(index=False))

    if predicted_delay is not None:
        print(f"\nModel-predicted trip delay: {predicted_delay:.1f} minutes")
        print("Estimated times apply the same predicted trip delay to each scheduled stop time.")
    else:
        print("\nML predicted delay: unavailable. Showing scheduled stop timings only.")

    # Historical actual timings are shown separately, never labelled as live timings.
    if "Actual_Arrival" in section.columns:
        print("\nREFERENCE TEMPLATE HISTORICAL/SIMULATED ACTUAL STOP TIMINGS (not live timings)")
        print(section[[
            "Stop_Sequence", "Stop_Name", "Actual_Arrival", "Actual_Departure"
        ]].to_string(index=False))

    print("\nNote: Dataset values are simulated historical records, not live GPS positions.")


# ============================================================
# 11. MAIN APPLICATION FLOW
# ============================================================

def main():
    print("=" * 65)
    print("KOZHIKODE BUS SEARCH AND JOURNEY SIMULATION")
    print("=" * 65)

    try:
        table1, table2, table3 = load_datasets()
    except Exception as error:
        print("\nDATA LOADING ERROR:", error)
        sys.exit(1)

    print("\nAll three datasets loaded successfully.")
    print("Table 1:", table1.shape)
    print("Table 2:", table2.shape)
    print("Table 3:", table3.shape)

    model, preprocessor, features = load_ml_components()

    inspect_datasets(table1, table2, table3)
    validate_service_stops(table2, table3)

    # Show stops that a passenger can search for.
    available_stops = sorted(table3["Stop_Name"].dropna().astype(str).str.strip().unique())
    print("\nAVAILABLE STOPS")
    print(", ".join(available_stops))

    print("\nENTER YOUR JOURNEY DETAILS")
    from_stop = input("From stop: ").strip()
    to_stop = input("To stop: ").strip()
    journey_date = ask_date("Journey date (DD-MM-YYYY): ")
    start_time = ask_time("Preferred travel time - FROM (HH:MM): ")
    end_time = ask_time("Preferred travel time - TO (HH:MM): ")

    if start_time > end_time:
        print("\nInvalid time range. The end time must be after the start time.")
        sys.exit(0)

    if normalise_text(from_stop) == normalise_text(to_stop):
        print("\nFrom stop and To stop cannot be the same.")
        sys.exit(0)

    try:
        temporary_table1, temporary_table3, template_date = generate_temporary_daily_data(
            table1, table3, journey_date
        )
    except Exception as error:
        print("\nTEMPORARY DATA GENERATION ERROR:", error)
        return

    results = search_available_buses(
        temporary_table1, temporary_table3,
        from_stop, to_stop, journey_date, start_time, end_time
    )

    if results.empty:
        print("\nNo matching simulated bus was found for this journey and time window.")
        print("Try another time window or check the stop names.")
        return

    # Display up to 10 matching buses (or fewer if fewer than 10 match).
    results = results.head(10).copy()
    display_bus_results(results)

    while True:
        choice = input("\nEnter the result number to select a bus (or Q to quit): ").strip()
        if choice.casefold() == "q":
            print("Search completed. Goodbye!")
            return
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            selected = results.iloc[int(choice) - 1]
            break
        print("Invalid selection. Please enter a displayed result number.")

    display_selected_journey(
        selected, temporary_table1, temporary_table3,
        model, preprocessor, features
    )

    print("\nSIMULATION COMPLETED!")
    print("Temporary simulated data existed only during this run and was not saved.")


if __name__ == "__main__":
    main()


