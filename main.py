# def process_fit_file(cloud_event):
#    print("Function is super live! Waiting for FIT file...")

import os
import io
import re
import fitparse
import pandas as pd
import functions_framework
from google.cloud import storage
from cloudevents.http import CloudEvent

# Initialize GCS client
storage_client = storage.Client()

@functions_framework.cloud_event
def process_fit_file(cloud_event: CloudEvent):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    # Only process .fit files
    if not (file_name.endswith('.fit')):
        print(f"Skipping non-fit file: {file_name}")
        return

    print(f"Processing: {file_name}")

    # 1. Download the file from GCS
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    file_content = blob.download_as_bytes()
    
    # 2. Parse the FIT file
    fitfile = fitparse.FitFile(io.BytesIO(file_content))
    records = []
    for record in fitfile.get_messages('record'):
        records.append({data.name: data.value for data in record})
    
    df = pd.DataFrame(records)
    
    # 3. Save as Parquet (optimized for analytics)

    # This will replace .fit, .FIT, .Fit, etc., with .parquet
    output_filename = re.sub(r'\.fit$', '.parquet', file_name, flags=re.IGNORECASE)

    # output_filename = file_name.replace('.fit', '.parquet')
    # Cast left_right_balance to string to prevent PyArrow schema mismatch with mixed types
    if 'left_right_balance' in df.columns:
            df['left_right_balance'] = df['left_right_balance'].astype(str)
    
    df.to_parquet(f"/tmp/{output_filename}")
    
    # 4. Upload to a 'processed' folder in the same bucket
    processed_blob = bucket.blob(f"processed/{output_filename}")
    processed_blob.upload_from_filename(f"/tmp/{output_filename}")
    
    print(f"Successfully processed and uploaded: {processed_blob.name}")

print("Function is done, let's hope it worked!...")
