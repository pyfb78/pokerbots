import pandas as pd

# Path to your .pkl file
pkl_file = "cfr_data.pkl"

# Load the Pickle file into a DataFrame
df = pd.read_pickle(pkl_file)

# Display the data
print(df.head())  # Shows the first few rows
