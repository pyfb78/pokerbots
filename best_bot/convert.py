import pandas as pd

# Read the CSV file
csv_file = "cfr_data.csv"
df = pd.read_csv(csv_file)

# Save as a PKL file
pkl_file = "cfr_data.pkl"
df.to_pickle(pkl_file)

print(f"CSV file '{csv_file}' has been converted to PKL file '{pkl_file}'.")
