import pandas as pd
import matplotlib.pyplot as plt
import os

# 1. Pick one of your converted files
# Change this to an actual filename you see in your csv_output folder!
file_path = 'csv_output/tp-523890_20250912.csv' 

if os.path.exists(file_path):
    # 2. Load the data
    df = pd.read_csv(file_path)

    # 3. Clean up (FIT files often have empty rows or columns)
    # We only want rows that actually have a timestamp and heart rate
    if 'power' in df.columns and 'tyme_breath_rate' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 4. Create the plot
        plt.figure(figsize=(10, 5))

        # Strip the units (the text after the space) and convert to a number
        df['power'] = pd.to_numeric(df['power'].str.split().str[0], errors='coerce')
        df['tyme_breath_rate'] = pd.to_numeric(df['tyme_breath_rate'].str.split().str[0], errors='coerce')

        # Drop any rows that couldn't be converted
        df = df.dropna(subset=['power', 'tyme_breath_rate'])

        plt.scatter(df['power'], df['tyme_breath_rate'], color='red', s=5, alpha=0.5, label='Breath Rate')
        
        plt.title('Breath Rate vs. Power')
        plt.xlabel('Power')
        plt.ylabel('BrPM')
        plt.grid(True)
        plt.legend()
        
        # 5. Save the graph as an image
        plt.savefig('breath_rate_plot.png')
        print("Graph saved as breath_rate_plot.png!")
        plt.show()
    else:
        print("Required columns (power/breath_rate) not found in this file.")
else:
    print(f"Could not find the file: {file_path}")