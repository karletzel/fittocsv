print("hello world") 

import csv
import os
from fitparse import FitFile

def convert_fit_to_csv(fit_file_path, csv_file_path):
    # Load the FIT file
    fit_file = FitFile(fit_file_path)
         
    with open(csv_file_path, mode='w', newline='') as file:
        writer = csv.writer(file)

        columns = set()
        
        for colcreate in fit_file.get_messages('record'): #Loop through messages in file                            
                for record_data in colcreate:  #Loop through records in each message
                    if record_data.name[:3] != "unk": columns.add(record_data.name)
        writer.writerow(sorted(columns))
        column_list = sorted(columns)
                 
        data = {} 
        for j in range(len(column_list)): data[column_list[j]]= " "
                                              
        for message in fit_file.get_messages('record'):  #Loop through messages in file     
               for i in range(len(column_list)): #Loop through total number of records 
                    for record_data in message:
                           if record_data.name == column_list[i]: # and record_data.units:
                             data[record_data.name] = record_data.value
                             #print("Recordata:",record_data.name, column_list[i], data[record_data.name])
                           #elif record_data.name == column_list[i]:
                            # data[record_data.name] = record_data.value
               writer.writerow(data.values())   

def process_folder(folder_path):
    output_folder = os.path.join(folder_path, 'csv_output')
    os.makedirs(output_folder, exist_ok=True)
    # List all FIT files in the folder
    for file in os.listdir(folder_path):
        if file.endswith(".FIT"):
            fit_file_path = os.path.join(folder_path, file)
            file_name_no_ext = os.path.splitext(file)[0]
            csv_file_path = os.path.join(output_folder,file_name_no_ext + '.csv')
            convert_fit_to_csv(fit_file_path, csv_file_path)
            print(f"Converted {fit_file_path} to {csv_file_path}")

# Replace with your folder path
folder_path = '.'
process_folder(folder_path)
print("That's all folks.")


#fit_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\files\\tp-523890_20250912.FIT'
#csv_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\output_5_CSV.csv'
#fit_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\TP10-22-16-27-16-835.FIT'
#csv_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\output_Three_CSV.csv'
#fit_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\TP10-31-13-56-25-487.FIT'
#csv_file_path = 'C:\\Users\\kretz\\Documents\\pythonwork\\output_TWO_CSV.csv'
#fit_file_path = 'TP10-22-16-27-16-835.FIT'
#fit_file_path = 'tp-523890_20250912.FIT'


# convert_fit_to_csv(fit_file_path, csv_file_path)


