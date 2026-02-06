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
    # We only want rows that actually have the data we want to plot 
    x_axis = 'power'
    y_axis = 'tyme_breath_rate'
    if x_axis in df.columns and y_axis in df.columns:
        df[x_axis] = pd.to_numeric(df[x_axis], errors="coerce")
        df[y_axis] = pd.to_numeric(df[y_axis], errors="coerce")
                                     
        # Drop any rows that couldn't be converted
        df = df.dropna(subset=[x_axis, y_axis])

        # 4. Create the plot
        plt.figure(figsize=(10, 5))

        # Strip the units (the text after the space) if they exist and convert to a number
        # df['power'] = pd.to_numeric(df['power'].str.split().str[0], errors='coerce')
        # df['tyme_breath_rate'] = pd.to_numeric(df['tyme_breath_rate'].str.split().str[0], errors='coerce')

        plt.scatter(df[x_axis], df[y_axis], color='red', s=5, alpha=0.5, label=y_axis)
        
        plt.title(f'{y_axis} vs {x_axis}')
        plt.xlabel(x_axis)
        plt.ylabel(y_axis)
        plt.grid(True)
        plt.legend()
        
        # 5. Save the graph as an image
        plt.savefig('breath_rate_plot.png')
        print("Graph saved as breath_rate_plot.png!")
        plt.show()
    else:
        print("Required columns not found in this file.")
else:
    print(f"Could not find the file: {file_path}")