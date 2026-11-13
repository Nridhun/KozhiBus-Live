from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Project directory
PROJECT_ROOT = Path(__file__).resolve().parent
# CSV files are directly inside the Data folder

#Python program needs to know where that folder is so it can read the CSV files
DATA_DIR = PROJECT_ROOT / 'Data'
Table_A = pd.read_csv(DATA_DIR /'BusTime_Tb1.csv')  #Containing 2 Year Bus Time Real data  information
Table_B = pd.read_csv(DATA_DIR /'RouteInfo_Tb2.csv') #Containing route,stop Information
Table_C = pd.read_csv(DATA_DIR /'Timeinfo_Tb3.csv') #Containing Journey information in Each route

#Data Cleaning Process -  Table 1
#---------------------------------
DTable1 = Table_A # Take a duplicated Data set and do The Operations
DTable2 = Table_B
DTable3 = Table_C
print(DTable1.head())
print(DTable1.info())
#Data set Containing 19 columns with float,int,string data types
print(DTable1.describe()) #nO USE Now Just did traditionally
print(DTable1.isnull().sum()) #Checking Missing Values
#There is some Missing Values in 'Distance_km  -- 9'  and 'Weather_Condition --2'
with pd.option_context('display.max_rows' , None, 'display.max_columns', None, 'display.width', 100): #Print null value without truncate
   print(DTable1[DTable1.Distance_km.isnull()==True])
# in here some Kilometer value is Missing but the value we can find from same table
#same Rote  consist of same Kilometer
DTable1["Distance_km"] = DTable1['Distance_km'].fillna(DTable1.groupby('Route_ID')["Distance_km"].transform("first")) #filled with same route id
print("Missing Values in Distance_km :  " ,DTable1['Distance_km'].isnull().sum())
#Clearing missing value in Weather_Condition
#whether is a String value  unable to do mean,median operations so we fill with frequent value.
DTable1['Weather_Condition'] = DTable1['Weather_Condition'].fillna(DTable1['Weather_Condition'].mode()[0])
print("Missing Values in Weather_Condition :  " ,DTable1['Weather_Condition'].isnull().sum())
#Missing Values Were Cleared
print("Duplicated value : ", DTable1.duplicated(subset=['Trip_ID'], keep=False).sum())
#checking DataTypes - if any numerical column are stored text,String format should correct
print(DTable1.dtypes) #now Date,time is in string format
DTable1['Journey_Date'] =  pd.to_datetime(DTable1['Journey_Date'],format='%d-%m-%Y')
DTable1[['Scheduled_Departure_Time','Actual_Departure_Time','Scheduled_Arrival_Time','Actual_Arrival_Time']] = DTable1[['Scheduled_Departure_Time','Actual_Departure_Time','Scheduled_Arrival_Time','Actual_Arrival_Time']].apply(
    lambda col: pd.to_datetime(col.astype(str).str.strip(), format='%H:%M', errors='coerce')
)
print(DTable1.dtypes)#Corrected all datatype - invalid columns
#Finding inconsistent value
print(DTable1[['Bus_Type','Weather_Condition','Traffic_Level','Festival_Eve']].apply(lambda col:col.unique())) #No inconsistent value Detected
print(DTable1['Starting_Stop'].unique()) #No inconsistent value Detected
#Finding OutLeyers
#Select all numerical columns
numeric_cols = DTable1.select_dtypes(include='number').columns
for col in numeric_cols:
   Q1 = DTable1[col].quantile(0.25)
   Q3 = DTable1[col].quantile(0.75)
   IQR = Q3 - Q1
   lower = Q1 - 1.5*IQR
   upper = Q3 + 1.5*IQR
   outliers = DTable1[(DTable1[col]<lower)|(DTable1[col]>upper)]
   print("Column  :",col)
   print("Number of potential outliers : ",len(outliers))
   print(outliers[[col]])

#In the Table there is outLeyers -  not droping or removing the out layer.
#Reason:these delays are realistic, real-world events rather than data-entry errors A bus taking 112 minutes instead of 79 minutes due to heavy rain, peak traffic, or festival days (like Onam or Christmas) is a valid pattern that model needs to learn.
#Dropping large delays teaches to machine learning model that extreme delays never happen. When deployed, the model will consistently underestimate arrival times during adverse conditions like storms or festival rush hours

#Checking for -ve,invali value
negatives = (DTable1[numeric_cols]<0).sum()
print("Negative values per column:\n", negatives[negatives > 0]) #No negative values in the table

#Checking - Inconsistent Relation Between columns
#1. Route vs. Start and End Stops
route_Mismatch = DTable1.groupby('Route_ID')[['Starting_Stop','Ending_Stop',]].nunique()
inconsistent_route = route_Mismatch[(route_Mismatch['Starting_Stop'] > 1) | (route_Mismatch['Ending_Stop'] > 1)]
#Count > 2: A third or fourth stop appears as a terminal under the same route code. This indicates an inconsistency, typo, or route coding error
print("Routes mapping to unexpected stop combinations:")
print(inconsistent_route)

#2.Route vs Distance Check
distance_check = DTable1.groupby(['Route_ID','Starting_Stop','Ending_Stop'])['Distance_km'].nunique()
inconsistent_distance = distance_check[distance_check>1]
print("Route segments with conflicting distance values:")
print(inconsistent_distance) #no external value found

#3 . Chronological Order of Timestamps
# Convert time strings to datetime (using dummy dates if only HH:MM is present)
actual_dep = pd.to_datetime(DTable1['Actual_Departure_Time'], format='%H:%M')
actual_arr = pd.to_datetime(DTable1['Actual_Arrival_Time'], format='%H:%M')
# Flag cases where arrival time is before departure without crossing midnight
time_inversion = DTable1[actual_arr < actual_dep]
print(f"Arrivals earlier than departures: {len(time_inversion)}")

#4 . Duration vs. Departure/Arrival Difference
computed_duration = (actual_arr - actual_dep).dt.total_seconds()/60
# Handle cases that crossed midnight (if arrival was on the next day)
computed_duration = computed_duration.apply(lambda x: x + 1440 if x < 0 else x)
# Check for rows where recorded duration does not match timestamp difference
duration_mismatch = DTable1[DTable1['Actual_Duration_Min'] != computed_duration]
print(f"Rows with mismatched actual duration: {len(duration_mismatch)}") #no MISMATCH
#5.Delay vs. Scheduled & Actual Differences
# Check consistency between actual duration, scheduled duration, and delay column
#----Mismatch found so do this step after clear value again

#Miss Match founded
#Verify after replacing
DTable1['Delay_Min'] = (DTable1['Actual_Duration_Min'] - DTable1['Scheduled_Duration_Min'])
computed_delay = DTable1['Actual_Duration_Min'] - DTable1['Scheduled_Duration_Min']
delay_mismatch = DTable1[DTable1['Delay_Min'] != computed_delay]
print(f"Rows where Delay_Min does not match difference: {len(delay_mismatch)}")
#6 . Physically Impossible Speed Check
# Implied speed in km/h
DTable1['Speed_kmh'] = np.where(
    DTable1['Actual_Duration_Min'] > 0,
    DTable1['Distance_km'] / (DTable1['Actual_Duration_Min'] / 60),
    np.nan
)

# Flag impossible speeds for city/regional buses
impossible_speed = DTable1[(DTable1['Speed_kmh'] > 140) | (DTable1['Speed_kmh'] < 3)]  #In night time Bus fill Ran very Fast so 140
print(f"Trips with impossible implied speeds: {len(impossible_speed)}")

#Table 3 have a unique Id Journey Id that i include in TB1 to combain
# 2. Extract a unique 1-to-1 mapping of Trip_ID to Journey_ID
journey_lookup = DTable3[['Trip_ID', 'Journey_ID']].drop_duplicates()

# 3. Perform the VLOOKUP (Left Join) into Table 1
DTable1 = DTable1.merge(
    journey_lookup,
    on='Trip_ID',
    how='left'
)





# 4. Verify the merge
print(DTable1[['Trip_ID', 'Journey_ID']].head())
print("Missing Journey_IDs:", DTable1['Journey_ID'].isnull().sum())
print(DTable1.head())

print(DTable1.info())

#----- DTable2 --Table no2
print(DTable2.head())
print(DTable2.info())
print(DTable2.isnull().sum())
#There is only  55 Value in the Table -Stop_Sequence colum only 13 value is available above 50% is missing so we drop the colum
DTable2 = DTable2.drop(columns=['Stop_Sequence'])
print(DTable2.columns)
print("duplicated values:" ,DTable2.duplicated().sum())#No duplicated Values
print(DTable2.dtypes)
#Finding inconsistent value
print(DTable2[['Starting_Stop','Ending_Stop','Stop_Name','Stop_Type','Ordinary_Stop','Limited_Stop_Stop','Superfast_Stop','Fast_Passenger_Stop']].apply(lambda col:col.unique()))
#no Inconsistent value found
#no outlyers,no -ve values (there is no numerical value in  table)
# Inconsistent Relation Between columns - no

#Data Cleaning Table no:3 DTable3
print(DTable3.columns)
print(DTable3.info())
print(DTable3.isnull().sum()) #No Missing Values
print("Duplicated value:",DTable3.duplicated().sum())
print(DTable3.dtypes)
#Date,Scheduled_Arrival,Actual_Arrival,Scheduled_Departure,Actual_Departure - those values conversion required
DTable3['Date'] =  pd.to_datetime(DTable3['Date'],format='%d-%m-%Y')                                               # [ERROOORRRRRRRRRRRRRRRRRRRR]
DTable3[['Scheduled_Arrival','Actual_Arrival','Scheduled_Departure','Actual_Departure']] = DTable3[['Scheduled_Arrival','Actual_Arrival','Scheduled_Departure','Actual_Departure']].apply(
    lambda col: pd.to_datetime(col.astype(str).str.strip(), format='%H:%M', errors='coerce')
)
with pd.option_context('display.max_rows' , None, 'display.max_columns', None, 'display.width', 100): #Print null value without truncate
 print(DTable3.head())

print(DTable3.dtypes)

#Checking is there any Relationship Between Route and Delay
route_delay = DTable1.groupby('Route_ID')['Delay_Min'].mean()
plt.figure(figsize=(10,5))
plt.bar(route_delay.index.astype(str), route_delay._values)

plt.title('Route and Delay Minutes')
plt.xlabel('Delay_Min')
plt.ylabel('Route_ID')
plt.show()
#**** Conclusion: The average delay is almost the same across all routes. No specific Route in the dataset appears to experience consistently higher delays. ***###

# Calculate average delay for each traffic level
traffic_delay = DTable1.groupby('Traffic_Level')['Delay_Min'].mean()

# Arrange traffic levels in order
traffic_order = ['Low', 'Moderate', 'High']
traffic_delay = traffic_delay.reindex(traffic_order)

# Create bar plot - checking Relation between Traffic level and Delay Min
plt.figure(figsize=(8, 5))
plt.bar(traffic_delay.index, traffic_delay.values)

plt.title('Traffic Level vs Average Bus Delay')
plt.xlabel('Traffic Level')
plt.ylabel('Average Delay (Minutes)')
plt.tight_layout()
plt.show()

# *** Conclusion : When the traffic level is high, bus delays tend to increase. However, low and moderate traffic levels show similar average delays.

# Count unique buses on each route

buses_per_route = DTable1.groupby('Route_ID')['Bus_ID'].nunique()

plt.figure(figsize=(10, 5))
plt.bar(buses_per_route.index.astype(str), buses_per_route.values)

plt.title('Distribution of Buses Across Routes')
plt.xlabel('Route ID')
plt.ylabel('Number of Unique Buses')
plt.tight_layout()
plt.show()

###*** Conclusion:Each of the 12 routes has a sufficient number of buses, with 35 buses operating across the network. No specific route has a shortage of buses. Therefore, passengers looking for connecting buses may experience shorter delays when transferring between routes.
# Calculate average delay for each weather condition
weather_delay = DTable1.groupby('Weather_Condition')['Delay_Min'].mean()
# Create bar plot
plt.figure(figsize=(8, 5))
plt.bar(weather_delay.index, weather_delay.values)

plt.title('Weather vs Average Bus Delay')
plt.xlabel('Weather Condition')
plt.ylabel('Average Delay (Minutes)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
#Conclusion:Rain increases the chances of bus delays. Heavy rain often leads to longer delays.

# Count trips by bus type
bus_type_counts = DTable1['Bus_Type'].value_counts()

# Create pie chart
plt.figure(figsize=(8, 8))

plt.pie(
    bus_type_counts.values,
    labels=bus_type_counts.index,
    autopct='%1.1f%%',
    startangle=90
)
plt.title('Total Distribution of Bus Types')
plt.tight_layout()
plt.show()
#*****Conclusion: Each bus type accounts for approximately 25% of the total number of buses, indicating that the distribution across all four bus types is almost equal.

#Distribution of stop types

service_columns = [
    'Ordinary_Stop',
    'Limited_Stop_Stop',
    'Superfast_Stop',
    'Fast_Passenger_Stop'
]

stop_counts = (DTable2[service_columns] == 'Yes').sum()

plt.figure(figsize=(9, 5))
plt.bar(
    ['Ordinary', 'Limited Stop', 'Superfast', 'Fast Passenger'],
    stop_counts.values
)

plt.title('Number of Stops Served by Each Bus Type')
plt.xlabel('Bus Service Type')
plt.ylabel('Number of Stops')
plt.xticks(rotation=20)
plt.tight_layout()
plt.show()
#Conclusion: Ordinary buses serve the highest number of stops, with more than 50 stops in total. Fast Passenger buses serve the fewest stops, as they generally stop only at major locations.

#delay at each stop
# Calculate arrival delay in minutes
DTable3['Arrival_Delay_Min'] = (
    DTable3['Actual_Arrival'] - DTable3['Scheduled_Arrival']
).dt.total_seconds() / 60

# Find average delay at each stop
stop_delay = (
    DTable3.groupby('Stop_Name')['Arrival_Delay_Min']
    .mean()
    .sort_values(ascending=False)
    .head(10)
)


plt.figure(figsize=(10, 6))
plt.barh(stop_delay.index, stop_delay.values)
plt.title('Top 10 Stops by Average Arrival Delay')
plt.xlabel('Average Arrival Delay (Minutes)')
plt.ylabel('Stop Name')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.show()
#Conclusion:Vadakara has the highest average arrival delay among the 10 stops shown, while Ulliyeri has the lowest. The differences are relatively small, with average delays ranging from about 3.7 to 4.7 minutes.It doesn't necessarily mean the stop itself causes delays; traffic, weather, and route conditions may contribute.



DTable3['Arrival_Delay_Min'] = (
    DTable3['Actual_Arrival'] -
    DTable3['Scheduled_Arrival']
).dt.total_seconds() / 60

DTable3['Date'] = pd.to_datetime(DTable3['Date'])

DTable3['Month'] = DTable3['Date'].dt.month

monthly_delay = DTable3.groupby('Month')['Arrival_Delay_Min'].mean()

plt.figure(figsize=(10, 5))
plt.plot(monthly_delay.index, monthly_delay.values, marker='o')
plt.title('Average Bus Arrival Delay by Month')
plt.xlabel('Month')
plt.ylabel('Average Delay (Minutes)')
plt.xticks(range(1, 13))
plt.grid(True)
plt.tight_layout()
plt.show()
#Conclusion:The average bus arrival delay varies across the months. April has the highest average delay at approximately 3.23 minutes, followed by December and September. November has the lowest average delay at around 2.89 minutes. Overall, the differences between months are relatively small.

DTable3.boxplot(
    column='Arrival_Delay_Min',
    by='Month',
    figsize=(10, 5)
)

plt.title('Bus Arrival Delay Distribution by Month')
plt.suptitle('')
plt.xlabel('Month')
plt.ylabel('Arrival Delay (Minutes)')
plt.tight_layout()
plt.show()
#Conclusion: Bus arrival delays show a similar distribution across all 12 months. Most delays are around 0–5 minutes, but every month has some outliers with delays exceeding 20 minutes. March has the highest observed delay, at approximately 39 minutes. This suggests that significant delays can occur throughout the year, rather than being limited to a particular month.
#Connect 3 Tables


def get_bus_information(trip_id):
    # Find the requested trip in Table 1
    bus_info = DTable1[
        DTable1["Trip_ID"] == trip_id
        ]

    # Check whether the trip exists
    if bus_info.empty:
        print("Trip ID not found.")
        return

    # Get the Route_ID from Table 1
    route_id = bus_info["Route_ID"].iloc[0]

    # ======================================
    # ACCESS ROUTE STOPS FROM TABLE 2
    # ======================================

    route_stops = DTable2[
        DTable2["Route_ID"] == route_id
        ]

    # ======================================
    # ACCESS TIMINGS FROM TABLE 3
    # ======================================

    trip_timings = DTable3[
        DTable3["Trip_ID"] == trip_id
        ]

    # ======================================
    # DISPLAY INFORMATION
    # ======================================

    print("\n========== BUS INFORMATION ==========")

    print(bus_info)

    print("\n========== ROUTE STOPS ==========")

    print(route_stops)

    print("\n========== STOP TIMINGS ==========")

    print(trip_timings)

'''
# Target variable
y = DTable1["Delay_Min"]

X = DTable1[
    [
        "Distance_km",
        "Scheduled_Duration_Min",
        "Traffic_Level",
        "Festival_Eve",
        "Bus_Type_Ordinary",
        "Bus_Type_Fast Passenger",
        "Bus_Type_Super Fast",
        "Bus_Type_Limited Stop",
        "Weather_Condition_Sunny",
        "Weather_Condition_Rainy"
    ]
]

# Check the features
print("Features (X):")
print(X.head())

# Check the target
print("\nTarget (y):")
print(y.head())

# Check the shapes
print("\nX Shape:", X.shape)
print("y Shape:", y.shape)




def get_bus_information(bus_id):

    # Step 1: Find the selected bus in Table 1
    bus_data = DTable1[
        DTable1["Bus_ID"] == bus_id
    ]

    if bus_data.empty:
        print("Bus not found!")
        return

    # Get the bus route
    route_id = bus_data.iloc[0]["Route_ID"]

    # Get the trip ID
    trip_id = bus_data.iloc[0]["Trip_ID"]

    # Get the Journey ID from Table 3
    journey_data = DTable3[
        DTable3["Trip_ID"] == trip_id
    ]

    if journey_data.empty:
        print("Journey information not found!")
        return

    journey_id = journey_data.iloc[0]["Journey_ID"]

    # Step 2: Retrieve route information from Table 2
    route_data = DTable2[
        DTable2["Route_ID"] == route_id
    ]

    # Step 3: Retrieve stop timing information from Table 3
    timing_data = DTable3[
        (DTable3["Journey_ID"] == journey_id) &
        (DTable3["Trip_ID"] == trip_id)
    ]

    # Display the information
    print("BUS INFORMATION")
    print(bus_data)

    print("\nCOMPLETE ROUTE")
    print(route_data)

    print("\nSTOP TIMINGS")
    print(timing_data)

    # Select a Bus_ID from your dataset
    selected_bus = "BUS001"

    # Retrieve all linked information
    get_bus_information(selected_bus)'''

print(DTable1.dtypes)

###Perform Feature Encoding

#Festival_Eve — Binary Encoding

DTable1 = pd.get_dummies(
    DTable1,
    columns=[
        "Weather_Condition",
        "Bus_Type",
        "Festival_Eve"
    ],
    dtype=int
)


with pd.option_context('display.max_rows' , None, 'display.max_columns', None, 'display.width', 100): #Print null value without truncate
 print(DTable1.head())



# 1. Extract Departure Hour
DTable1["Departure_Hour"] = (
    DTable1["Scheduled_Departure_Time"].dt.hour
)


# 2. Extract Arrival Hour
DTable1["Arrival_Hour"] = (
    DTable1["Scheduled_Arrival_Time"].dt.hour
)


# 3. Extract Day of Week
# Monday = 0, Sunday = 6

DTable1["Day_of_Week"] = (
    DTable1["Journey_Date"].dt.day_of_week
)


# 4. Identify Weekends
# Saturday = 5, Sunday = 6

DTable1["Is_Weekend"] = (
    DTable1["Journey_Date"].dt.day_of_week >= 5
).astype(int)



# 5. Extract Month

DTable1["Journey_Month"] = (
    DTable1["Journey_Date"].dt.month
)


# 6. Identify Peak Departure Hours
# Morning: 7 AM - 10 AM
# Evening: 4 PM - 7 PM

DTable1["Is_Peak_Hour"] = (
    DTable1["Departure_Hour"].between(7, 10) |
    DTable1["Departure_Hour"].between(16, 19)
).astype(int)


# 7. Calculate Scheduled Average Speed

DTable1["Scheduled_Speed_kmh"] = (
    DTable1["Distance_km"] /
    (DTable1["Scheduled_Duration_Min"] / 60)
)

print(DTable1[[
    "Departure_Hour",
    "Arrival_Hour",
    "Day_of_Week",
    "Is_Weekend",
    "Journey_Month",
    "Is_Peak_Hour",
    "Scheduled_Speed_kmh"
]].head(10))

print(DTable1.columns.tolist())

# ==========================================
# MODEL A - TARGET VARIABLE
# ==========================================

# Calculate arrival delay in minutes

DTable1["Arrival_Delay_Min"] = (
    DTable1["Actual_Arrival_Time"] -
    DTable1["Scheduled_Arrival_Time"]
).dt.total_seconds() / 60


# Check target variable

print(DTable1["Arrival_Delay_Min"].describe())

print("\nSample values:")
print(DTable1[[
    "Scheduled_Arrival_Time",
    "Actual_Arrival_Time",
    "Arrival_Delay_Min",
    "Delay_Min"
]].head(10))

print("Arrival Delay dtype:",
      DTable1["Arrival_Delay_Min"].dtype)

print("Delay Min dtype:",
      DTable1["Delay_Min"].dtype)

print("\nAre values equal?")

print(
    np.allclose(
        DTable1["Arrival_Delay_Min"],
        DTable1["Delay_Min"],
        equal_nan=True
    )
)

# Find rows where both columns differ
different_rows = DTable1[
    ~np.isclose(
        DTable1["Arrival_Delay_Min"],
        DTable1["Delay_Min"],
        equal_nan=True
    )
]
#FINDING THE MISSMATCHED VALUE
print("Number of different rows:", len(different_rows))

print(
    different_rows[
        [
            "Arrival_Delay_Min",
            "Delay_Min"
        ]
    ].head(20)
)

different_rows = DTable1[
    ~np.isclose(
        DTable1["Arrival_Delay_Min"],
        DTable1["Delay_Min"],
        equal_nan=True
    )
]

print(different_rows[
    [
        "Arrival_Delay_Min",
        "Delay_Min"
    ]
].head(20))

# Display all column names
print("Table 3 Columns:")
print(DTable3.columns.tolist())


# Display first 10 rows
print("\nTable 3 Sample:")
print(DTable3.head(10).to_string())


# Display data types
print("\nTable 3 Data Types:")
print(DTable3.dtypes)

print("Table 2 Columns:")
print(DTable2.columns.tolist())

print("\nTable 2 Sample:")
print(DTable2.head(10).to_string())

# Sort stops in journey order

DTable3 = DTable3.sort_values(
    ["Journey_ID", "Stop_Sequence"]
).copy()


# 1. Calculate current delay

DTable3["Current_Delay_Min"] = (
    DTable3["Actual_Arrival"] -
    DTable3["Scheduled_Arrival"]
).dt.total_seconds() / 60


# 2. Calculate final arrival delay for each journey

DTable3["Final_Arrival_Delay_Min"] = (
    DTable3.groupby("Journey_ID")["Current_Delay_Min"]
    .transform("last")
)


# 3. Create target variable

DTable3["Remaining_Journey_Delay_Min"] = (
    DTable3["Final_Arrival_Delay_Min"] -
    DTable3["Current_Delay_Min"]
)
print(DTable3[
    [
        "Journey_ID",
        "Stop_Name",
        "Stop_Sequence",
        "Current_Delay_Min",
        "Final_Arrival_Delay_Min",
        "Remaining_Journey_Delay_Min"
    ]
].head(20))

print(DTable3["Remaining_Journey_Delay_Min"].describe())

print(
    "Missing target values:",
    DTable3["Remaining_Journey_Delay_Min"].isna().sum()
)
print("Negative target values:")
print(
    (DTable3["Remaining_Journey_Delay_Min"] < 0).sum()
)

print("\nZero target values:")
print(
    (DTable3["Remaining_Journey_Delay_Min"] == 0).sum()
)

print("\nPositive target values:")
print(
    (DTable3["Remaining_Journey_Delay_Min"] > 0).sum()
)
#Feature Selection

print(DTable3.columns.tolist())
for col in DTable3.columns:
    print(col)

    # Create Next_Stop
DTable3["Next_Stop"] = (
    DTable3.groupby("Journey_ID")["Stop_Name"].shift(-1)
)

    # Reset index
DTable3 = DTable3.reset_index(drop=True)

    # Display result
print(DTable3[["Journey_ID", "Stop_Name", "Next_Stop"]].head(15))

y = DTable3["Remaining_Journey_Delay_Min"]

# Date-based features
DTable3["Day_of_Week"] = DTable3["Date"].dt.dayofweek

DTable3["Month"] = DTable3["Date"].dt.month

DTable3["Is_Weekend"] = (
    DTable3["Day_of_Week"] >= 5
).astype(int)


# Convert scheduled arrival into minutes after midnight
DTable3["Scheduled_Arrival_Min"] = (
    DTable3["Scheduled_Arrival"].dt.hour * 60 +
    DTable3["Scheduled_Arrival"].dt.minute
)


# Convert actual arrival into minutes after midnight
DTable3["Actual_Arrival_Min"] = (
    DTable3["Actual_Arrival"].dt.hour * 60 +
    DTable3["Actual_Arrival"].dt.minute
)

feature_columns = [

    # Bus information
    "Bus_Type",
    "Route_ID",

    # Journey information
    "Starting_Stop",
    "Ending_Stop",

    # Current stop information
    "Stop_Name",
    "Next_Stop",
    "Stop_Sequence",

    # Time information
    "Day_of_Week",
    "Month",
    "Is_Weekend",
    "Scheduled_Arrival_Min",
    "Actual_Arrival_Min",

    # Current delay
    "Current_Delay_Min"
]

X = DTable3[feature_columns].copy()

# Target
y = DTable3["Remaining_Journey_Delay_Min"].copy()

valid_target_mask = y.notna()
DTable3 = DTable3.loc[valid_target_mask].copy()
X = X.loc[valid_target_mask].copy()
y = y.loc[valid_target_mask].copy()

print("Features:")
print(X.columns.tolist())

print("\nFeature Data Types:")
print(X.dtypes)

print("\nMissing Values:")
print(X.isnull().sum())

print("\nTarget Shape:", y.shape)
print("Feature Shape:", X.shape)

# Handle missing Next_Stop

X = X.copy()

X["Next_Stop"] = X["Next_Stop"].fillna("Destination")


#Split the dataset


splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.2,
    random_state=42
)

train_idx, test_idx = next(
    splitter.split(
        X,
        y,
        groups=DTable3["Journey_ID"]
    )
)

X_train = X.iloc[train_idx]
X_test = X.iloc[test_idx]

y_train = y.iloc[train_idx]
y_test = y.iloc[test_idx]

print("Training Features:", X_train.shape)
print("Testing Features:", X_test.shape)

print("Training Target:", y_train.shape)
print("Testing Target:", y_test.shape)
print("Training journeys:",
      DTable3.iloc[train_idx]["Journey_ID"].nunique())

print("Testing journeys:",
      DTable3.iloc[test_idx]["Journey_ID"].nunique())

print("Missing values in training:")
print(X_train.isnull().sum().sum())

print("Missing values in testing:")
print(X_test.isnull().sum().sum())

print(X_train.dtypes)

# Identify categorical columns
categorical_columns = X_train.select_dtypes(
    include=['object']
).columns.tolist()

# Identify numerical columns
numerical_columns = X_train.select_dtypes(
    include=['int64', 'float64']
).columns.tolist()

print("Categorical Features:", categorical_columns)
print("\nNumerical Features:", numerical_columns)

# Preprocessing

preprocessor = ColumnTransformer(
    transformers=[
        ('categorical', OneHotEncoder(handle_unknown='ignore'), categorical_columns),
        ('numerical', StandardScaler(), numerical_columns)
    ]
)
# Identify categorical features
categorical_columns = X_train.select_dtypes(
    include=['object']
).columns.tolist()

# Identify numerical features
numerical_columns = X_train.select_dtypes(
    include=['number']
).columns.tolist()

print("Categorical Features:", categorical_columns)
print("\nNumerical Features:", numerical_columns)

print("\nTotal Features:", len(categorical_columns) + len(numerical_columns))
# Learn encoding from training data
X_train_encoded = preprocessor.fit_transform(X_train)

# Apply the same encoding to testing data
X_test_encoded = preprocessor.transform(X_test)

print("Training Shape:", X_train_encoded.shape)
print("Testing Shape:", X_test_encoded.shape)
# Get encoded feature names

encoded_feature_names = preprocessor.get_feature_names_out()

print("Total Encoded Features:", len(encoded_feature_names))

print("\nEncoded Feature Names:")
print(encoded_feature_names)

from sklearn.ensemble import RandomForestRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# Create Random Forest model

model = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    random_state=42,
    n_jobs=-1
)

# Train the model

# Train the model

model.fit(X_train_encoded, y_train)

# Predict remaining journey delay

y_pred = model.predict(X_test_encoded)

# Calculate evaluation metrics

mae = mean_absolute_error(y_test, y_pred)

mse = mean_squared_error(y_test, y_pred)

rmse = mse ** 0.5

r2 = r2_score(y_test, y_pred)

print("Model Evaluation")

print("MAE:", mae)
print("MSE:", mse)
print("RMSE:", rmse)
print("R2 Score:", r2)

# Compare actual and predicted values

comparison = pd.DataFrame({
    "Actual_Delay": y_test.values,
    "Predicted_Delay": y_pred
})

comparison["Prediction_Error"] = (
    comparison["Actual_Delay"] - comparison["Predicted_Delay"]
)

print(comparison.head(20))

import matplotlib.pyplot as plt

plt.figure(figsize=(8, 6))

plt.scatter(y_test, y_pred, alpha=0.3)

plt.xlabel("Actual Delay (Minutes)")
plt.ylabel("Predicted Delay (Minutes)")
plt.title("Actual vs Predicted Bus Delay")

plt.show()

plt.figure(figsize=(8, 6))

plt.scatter(y_test, y_pred, alpha=0.3)

# Ideal prediction line
min_value = min(y_test.min(), y_pred.min())
max_value = max(y_test.max(), y_pred.max())

plt.plot(
    [min_value, max_value],
    [min_value, max_value],
    'r--',
    label="Perfect Prediction"
)

plt.xlabel("Actual Delay (Minutes)")
plt.ylabel("Predicted Delay (Minutes)")

plt.title("Actual vs Predicted Bus Delay")
plt.legend()
plt.show()
residuals = y_test.values - y_pred

plt.figure(figsize=(10, 5))

plt.hist(residuals, bins=50, edgecolor="black")

plt.axvline(0, color="red", linestyle="--")

plt.xlabel("Prediction Error (Minutes)")
plt.ylabel("Frequency")

plt.title("Distribution of Prediction Errors")

plt.show()


# Feature Importance Analysis

import pandas as pd
import matplotlib.pyplot as plt

# Get feature importance from Random Forest
importance_scores = model.feature_importances_

# Create a DataFrame
feature_importance = pd.DataFrame({
    'Feature': encoded_feature_names,
    'Importance': importance_scores
})

# Sort features by importance
feature_importance = feature_importance.sort_values(
    by='Importance',
    ascending=False
)


# Display top 20 important features

print("\nTop 20 Important Features:")

print(feature_importance.head(20).to_string(index=False))

# Plot top 20 features

top_features = feature_importance.head(20)

plt.figure(figsize=(12, 8))

plt.barh(
    top_features['Feature'],
    top_features['Importance']
)

plt.gca().invert_yaxis()

plt.xlabel("Importance Score")
plt.ylabel("Feature Names")

plt.title("Top 20 Feature Importance - Random Forest")

plt.tight_layout()

plt.show()

from sklearn.pipeline import Pipeline
from sklearn.inspection import permutation_importance

# Combine our already-trained preprocessing and model
evaluation_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('model', model)
])

# Calculate permutation importance
permutation_result = permutation_importance(
    evaluation_pipeline,
    X_test,
    y_test,
    n_repeats=10,
    random_state=42,
    scoring='neg_mean_absolute_error',
    n_jobs=-1
)

# Create a DataFrame
permutation_df = pd.DataFrame({
    'Feature': X_test.columns,
    'Importance': permutation_result.importances_mean
})

# Sort by importance
permutation_df = permutation_df.sort_values(
    by='Importance',
    ascending=False
)

print("\nPermutation Importance:")
print(permutation_df.to_string(index=False))


# Display feature importance
print("\nFeature Importance:")
print(feature_importance)

# Visualize top 20 features
top_features = feature_importance.head(20)

plt.figure(figsize=(10, 8))

plt.barh(
    top_features['Feature'],
    top_features['Importance']
)

plt.gca().invert_yaxis()

plt.xlabel("Importance Score")
plt.ylabel("Features")
plt.title("Random Forest - Feature Importance")

plt.tight_layout()
plt.show()


# Visualize Permutation Importance

top_permutation = permutation_df.head(10)

plt.figure(figsize=(10, 6))

plt.barh(
    top_permutation['Feature'],
    top_permutation['Importance']
)

plt.gca().invert_yaxis()

plt.xlabel("Increase in MAE (Minutes)")
plt.ylabel("Features")

plt.title("Permutation Feature Importance")

plt.tight_layout()

plt.show()
# Inspect original model input features

print("\nFeatures used by the model:")

for column in X_train.columns:
    print(column)

#count 13 features in the screenshot, not 14.


# ==========================================
# INSPECT INPUT FEATURES AND TARGET VARIABLE
# ==========================================

print("\n========== DATASET INSPECTION ==========")

print("\nDataset Columns:")
print(DTable1.columns.tolist())

print("\nDataset Shape:")
print(DTable1.shape)


# ==========================================
# INPUT FEATURES (X)
# ==========================================

print("\n========== INPUT FEATURES (X) ==========")

print("X Shape:", X.shape)

print("\nFeatures used by the model:")

for column in X.columns:
    print(column)


# ==========================================
# TARGET VARIABLE (y)
# ==========================================

print("\n========== TARGET VARIABLE (y) ==========")

print("Target Name:", y.name)
print("Target Shape:", y.shape)

print("\nTarget Statistics:")
print(y.describe())


# ==========================================
# CHECK MISSING VALUES
# ==========================================

print("\n========== MISSING VALUES ==========")

print("\nMissing values in X:")
print(X.isnull().sum())

print("\nMissing values in y:")
print(y.isnull().sum())


# ==========================================
# CHECK TARGET DISTRIBUTION
# ==========================================

print("\n========== TARGET DISTRIBUTION ==========")

print(y.value_counts().head(20))

print("\n========== INSPECTION COMPLETED ==========")

print("Dtable1 Shape:", DTable1.shape)

print("X Shape:", X.shape)

print("y Shape:", y.shape)

print("\nX Index:")
print(X.index[:10])

print("\ny Index:")
print(y.index[:10])

print("\nAre X and y indexes matching?")
print(X.index.equals(y.index))

print("\n========== DATASET COMPARISON ==========")

print("DTable1 Shape:", DTable1.shape)
print("DTable3 Shape:", DTable3.shape)

print("X Shape:", X.shape)
print("y Shape:", y.shape)

print("\nX and DTable3 indexes match:")
print(X.index.equals(DTable3.index))

print("\ny and DTable3 indexes match:")
print(y.index.equals(DTable3.index))

print("\n========== TARGET VALIDATION ==========")

# Check target calculation
expected_target = (
    DTable3["Final_Arrival_Delay_Min"]
    - DTable3["Current_Delay_Min"]
)

print(
    "Target calculation correct:",
    DTable3["Remaining_Journey_Delay_Min"].equals(expected_target)
)

# Check whether future information is in X
print(
    "\nFinal_Arrival_Delay_Min in X:",
    "Final_Arrival_Delay_Min" in X.columns
)

print(
    "Remaining_Journey_Delay_Min in X:",
    "Remaining_Journey_Delay_Min" in X.columns
)

print("Unique Journey IDs:", DTable3["Journey_ID"].nunique())

print("Unique Trip IDs:", DTable3["Trip_ID"].nunique())

print("\nRecords per Journey:")
print(DTable3["Journey_ID"].value_counts().describe())

print("\nRecords per Trip:")
print(DTable3["Trip_ID"].value_counts().describe())

print("Unique Journey IDs:",
      DTable3["Journey_ID"].nunique())

print("Unique Trip IDs:",
      DTable3["Trip_ID"].nunique())

print("\nJourney_ID and Trip_ID relationship:")

print(
    DTable3.groupby("Trip_ID")["Journey_ID"].nunique().describe()
)

print(
    DTable3.groupby("Journey_ID")["Trip_ID"].nunique().describe()
)

print(DTable3["Date"].dtype)

print(DTable3["Date"].min())

print(DTable3["Date"].max())

print(DTable3["Date"].nunique())

#Inspect yearly distribution

print("\nRecords per year:")

print(DTable3["Date"].dt.year.value_counts().sort_index())

#Journey and stop sequence validation

print(
    DTable3[
        [
            "Journey_ID",
            "Trip_ID",
            "Stop_Name",
            "Stop_Sequence",
            "Current_Delay_Min"
        ]
    ].head(30)
)

#Inspect  final features

print("FEATURE COLUMNS:")
print(X.columns.tolist())

print("\nFEATURE DATA TYPES:")
print(X.dtypes)

print("\nTARGET VARIABLE:")
print(y.name)

print("\nTARGET DATA TYPE:")
print(y.dtype)



# ==========================================
# STEP 1: FEATURE INSPECTION
# ==========================================

print("\n========== FEATURE INSPECTION ==========")

# 1. Display all feature names
print("\nFeature Columns:")
print(X.columns.tolist())

# 2. Display data types
print("\nFeature Data Types:")
print(X.dtypes)

# 3. Separate numerical and categorical features
numerical_features = X.select_dtypes(
    include=["int64", "float64"]
).columns.tolist()

categorical_features = X.select_dtypes(
    include=["object", "category", "bool"]
).columns.tolist()

print("\nNumerical Features:")
print(numerical_features)

print("\nCategorical Features:")
print(categorical_features)

# 4. Check missing values
print("\nMissing Values:")
print(X.isnull().sum())

# 5. Count unique values in each feature
print("\nUnique Values:")
print(X.nunique())

# 6. Display feature summary
print("\nFeature Summary:")
print(
    X.describe(include="all").T
)


# CATEGORICAL FEATURE SUMMARY

for col in categorical_features:

    print("\n----------------------------")
    print("Feature:", col)

    print("Unique Categories:", X[col].nunique())

    print("\nCategory Distribution:")
    print(X[col].value_counts())

    print("\nMissing Values:", X[col].isnull().sum())

    # ==========================================
    # FEATURE PREPROCESSING
    # ==========================================

    # 1. Identify categorical and numerical features

categorical_features = X.select_dtypes(
    include=["object", "category"]
).columns.tolist()

numerical_features = X.select_dtypes(include=["number"]).columns.tolist()

print("Categorical Features:")
print(categorical_features)

print("\nNumerical Features:")
print(numerical_features)

    # 2. Display feature counts

print("\nTotal Categorical Features:",
      len(categorical_features))

print("Total Numerical Features:",
      len(numerical_features))

print("Total Features:",
      len(X.columns))

from sklearn.model_selection import train_test_split

# Split features and target into training and testing data

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

# Display dataset dimensions

print("\nTraining Data:")
print("X_train:", X_train.shape)
print("y_train:", y_train.shape)

print("\nTesting Data:")
print("X_test:", X_test.shape)
print("y_test:", y_test.shape)

#Correct the split using Journey_ID

from sklearn.model_selection import GroupShuffleSplit

# Split dataset based on unique journeys

splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.20,
    random_state=42
)

train_idx, test_idx = next(
    splitter.split(
        X,
        y,
        groups=DTable3.loc[X.index, "Journey_ID"]
    )
)

# Create training and testing datasets

X_train = X.iloc[train_idx]
X_test = X.iloc[test_idx]

y_train = y.iloc[train_idx]
y_test = y.iloc[test_idx]

# Display dimensions

print("Training Data:", X_train.shape)
print("Testing Data:", X_test.shape)

print("\nUnique Training Journeys:",
      DTable3.iloc[train_idx]["Journey_ID"].nunique())

print("Unique Testing Journeys:",
      DTable3.iloc[test_idx]["Journey_ID"].nunique())

# Check for overlapping journeys

train_journeys = set(
    DTable3.iloc[train_idx]["Journey_ID"]
)

test_journeys = set(
    DTable3.iloc[test_idx]["Journey_ID"]
)

print("\nOverlapping Journeys:",
      len(train_journeys.intersection(test_journeys)))

# ==========================================
# FEATURE ENCODING AND SCALING
# ==========================================

from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

# 1. Create preprocessing transformer

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features
        ),
        (
            "numerical",
            StandardScaler(),
            numerical_features
        )
    ]
)

# 2. Fit and transform training data

X_train_processed = preprocessor.fit_transform(X_train)

# 3. Transform testing data

X_test_processed = preprocessor.transform(X_test)

# 4. Display results

print("Original Training Shape:", X_train.shape)

print("Processed Training Shape:", X_train_processed.shape)

print("\nOriginal Testing Shape:", X_test.shape)

print("Processed Testing Shape:", X_test_processed.shape)

print("\nTarget Shape:", y_train.shape)

# MODEL TRAINING

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor

# 1. Create baseline model

baseline_model = DummyRegressor(strategy="mean")

# 2. Train baseline model

baseline_model.fit(X_train_processed, y_train)

# 3. Create Random Forest model

rf_model = RandomForestRegressor(
    n_estimators=100,
    max_depth=20,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)

# 4. Train Random Forest

rf_model.fit(X_train_processed, y_train)

print("Both models trained successfully!")

# MODEL PREDICTION

# 1. Baseline predictions
baseline_predictions = baseline_model.predict(X_test_processed)

# 2. Random Forest predictions
rf_predictions = rf_model.predict(X_test_processed)

# 3. Display sample predictions

print("\nACTUAL VS PREDICTED DELAYS")

comparison = pd.DataFrame({
    "Actual_Delay": y_test.values[:10],
    "Baseline_Prediction": baseline_predictions[:10],
    "RandomForest_Prediction": rf_predictions[:10]
})

print(comparison)


# MODEL EVALUATION

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score

import numpy as np

# 1. Baseline Evaluation

baseline_mae = mean_absolute_error(
    y_test, baseline_predictions
)

baseline_rmse = np.sqrt(
    mean_squared_error(y_test, baseline_predictions)
)

baseline_r2 = r2_score(
    y_test, baseline_predictions
)


# 2. Random Forest Evaluation

rf_mae = mean_absolute_error(
    y_test, rf_predictions
)

rf_rmse = np.sqrt(
    mean_squared_error(y_test, rf_predictions)
)

rf_r2 = r2_score(
    y_test, rf_predictions
)


# 3. Display Results

print("\nMODEL EVALUATION RESULTS")

results = pd.DataFrame({
    "Metric": ["MAE", "RMSE", "R2"],
    "Baseline": [
        baseline_mae,
        baseline_rmse,
        baseline_r2
    ],
    "Random Forest": [
        rf_mae,
        rf_rmse,
        rf_r2
    ]
})

print(results)

# ==========================================
# FEATURE IMPORTANCE ANALYSIS
# ==========================================

# 1. Extract feature names
feature_names = preprocessor.get_feature_names_out()

# 2. Get Random Forest feature importance
importance = rf_model.feature_importances_

# 3. Create DataFrame
feature_importance = pd.DataFrame({
    "Feature": feature_names,
    "Importance": importance
})

# 4. Sort by importance
feature_importance = feature_importance.sort_values(
    by="Importance",
    ascending=False
)

# 5. Display top 20 features
print("\nTOP 20 IMPORTANT FEATURES")

print(feature_importance.head(20).to_string(index=False))

import matplotlib.pyplot as plt

# Select top 15 features
top_features = feature_importance.head(15)

# Create figure
plt.figure(figsize=(12, 8))

# Horizontal bar chart
plt.barh(
    top_features["Feature"],
    top_features["Importance"]
)

# Highest importance at the top
plt.gca().invert_yaxis()

# Add labels
plt.xlabel("Feature Importance")
plt.ylabel("Features")
plt.title("Top 15 Features Affecting Bus Delay Prediction")

# Display chart
plt.tight_layout()
plt.show()

# ==========================================
# DATA LEAKAGE INVESTIGATION
# ==========================================

# 1. Check target variable
print("\nTARGET VARIABLE")
print(y.name)

# 2. Check all input features
print("\nFEATURES USED BY MODEL")

print(X.columns.tolist())

# 3. Select important columns for investigation
audit_columns = [
    "Journey_ID",
    "Stop_Sequence",
    "Stop_Name",
    "Next_Stop",
    "Scheduled_Arrival_Min",
    "Actual_Arrival_Min",
    "Current_Delay_Min",
    "Remaining_Journey_Delay_Min"
]

# 4. Check which columns exist
available_columns = [
    col for col in audit_columns
    if col in DTable3.columns
]

print("\nAVAILABLE AUDIT COLUMNS")

print(available_columns)

# 5. Select one complete journey
journey_id = (
    DTable3.groupby("Journey_ID")
    .size()
    .idxmax()
)

sample_journey = DTable3[
    DTable3["Journey_ID"] == journey_id
].sort_values("Stop_Sequence")

# 6. Display journey information
print("\nSAMPLE JOURNEY INFORMATION")

print(
    sample_journey[available_columns]
    .to_string(index=False)
)

# Check model features before saving

print("\nMODEL FEATURE AUDIT")

print("Total Features:", len(X.columns))

print("\nFeatures Used:")
print(X.columns.tolist())

print("\nTarget Leakage Check:")
print("Target in Features:",
      "Remaining_Journey_Delay_Min" in X.columns)

print("Journey_ID in Features:",
      "Journey_ID" in X.columns)


# ==========================================
# SAVE TRAINED MODEL AND PREPROCESSOR
# ==========================================

import os
import joblib

# 1. Create Models folder
os.makedirs("Models", exist_ok=True)

# 2. Save Random Forest model
joblib.dump(
    rf_model,
    "Models/live_delay_model.pkl"
)

# 3. Save preprocessing pipeline
joblib.dump(
    preprocessor,
    "Models/live_delay_preprocessor.pkl"
)

# 4. Save feature information
joblib.dump(
    X.columns.tolist(),
    "Models/live_delay_features.pkl"
)

print("\nMODEL SAVING COMPLETED!")

print("Random Forest model saved.")
print("Preprocessor saved.")
print("Feature information saved.")


# =====================================
# TEST SAVED MODEL LOADING
# =====================================

import joblib

# Load saved model
loaded_model = joblib.load(
    "Models/live_delay_model.pkl"
)

# Load saved preprocessor
loaded_preprocessor = joblib.load(
    "Models/live_delay_preprocessor.pkl"
)

# Load saved features
loaded_features = joblib.load(
    "Models/live_delay_features.pkl"
)

print("\nMODEL LOADING TEST")

print("Model:", type(loaded_model))
print("Preprocessor:", type(loaded_preprocessor))
print("Total Features:", len(loaded_features))

print("\nAll saved files loaded successfully!")
# TEST SAVED MODEL PREDICTION

# Select one sample from testing data
sample_input = X_test.iloc[[0]]

# Apply saved preprocessing
sample_processed = loaded_preprocessor.transform(
    sample_input[loaded_features]
)

# Predict remaining journey delay
sample_prediction = loaded_model.predict(
    sample_processed
)

print("\nSAVED MODEL PREDICTION TEST")

print("Input Data:")
print(sample_input)

print("Predicted Remaining Delay:",
      sample_prediction[0], "minutes")


# Predict remaining journey delay
