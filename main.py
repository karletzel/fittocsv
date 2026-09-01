import hashlib
import io
import os
import re
from decimal import Decimal
from numbers import Real

import fitparse
import functions_framework
import pandas as pd
from cloudevents.http import CloudEvent
from google.cloud import storage


FIELD_DTYPES = {
    "heart_rate": "float64",
}

# A fixed schema prevents different kinds of workouts from producing incompatible
# Parquet schemas when some FIT fields are absent.
METADATA_DTYPES = {
    "workout_id": "string",
    "source_bucket": "string",
    "source_file": "string",
    "sport": "string",
    "sub_sport": "string",
    "start_time": "datetime64[ns, UTC]",
    "end_time": "datetime64[ns, UTC]",
    "total_elapsed_time": "float64",
    "total_timer_time": "float64",
    "total_distance": "float64",
    "total_calories": "float64",
    "avg_heart_rate": "float64",
    "max_heart_rate": "float64",
    "avg_speed": "float64",
    "max_speed": "float64",
    "total_ascent": "float64",
    "total_descent": "float64",
    "avg_cadence": "float64",
    "max_cadence": "float64",
    "avg_power": "float64",
    "max_power": "float64",
    "normalized_power": "float64",
    "training_stress_score": "float64",
    "intensity_factor": "float64",
    "avg_temperature": "float64",
    "min_temperature": "float64",
    "max_temperature": "float64",
    "manufacturer": "string",
    "product": "string",
    "serial_number": "string",
    "device_created_at": "datetime64[ns, UTC]",
}

SESSION_FIELDS = tuple(
    name
    for name in METADATA_DTYPES
    if name
    not in {
        "workout_id",
        "source_bucket",
        "source_file",
        "end_time",
        "min_temperature",
        "manufacturer",
        "product",
        "serial_number",
        "device_created_at",
    }
)


def normalize_fit_value(value):
    """Return a value with a stable type suitable for a Parquet column."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (Real, Decimal)):
        return float(value)
    return value


def extract_record(record):
    """Extract a FIT message while normalizing every numeric field."""
    return {field.name: normalize_fit_value(field.value) for field in record}


def enforce_field_dtypes(df):
    """Apply canonical dtypes that must be identical in every output file."""
    for field_name, dtype in FIELD_DTYPES.items():
        if field_name in df.columns:
            df[field_name] = pd.to_numeric(df[field_name], errors="coerce").astype(dtype)
    return df


def build_records_dataframe(records, file_name, workout_id):
    """Build the record-level time series written to processed/data."""
    if not records:
        raise ValueError(f"No FIT record messages found in {file_name}")

    records_df = enforce_field_dtypes(pd.DataFrame(records))
    if "timestamp" not in records_df.columns or records_df["timestamp"].isna().all():
        raise ValueError(f"FIT record messages have no timestamps in {file_name}")

    records_df["timestamp"] = pd.to_datetime(
        records_df["timestamp"], errors="coerce", utc=True
    )
    if records_df["timestamp"].isna().all():
        raise ValueError(f"FIT record timestamps could not be decoded in {file_name}")

    records_df.insert(0, "workout_id", workout_id)
    records_df.insert(1, "source_file", file_name)
    if "left_right_balance" in records_df.columns:
        records_df["left_right_balance"] = records_df["left_right_balance"].astype(str)
    return records_df


def workout_id_for(bucket_name, file_name):
    """Return a stable join key for all outputs produced from a GCS object."""
    identity = f"gs://{bucket_name}/{file_name}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


def first_message(fitfile, message_name):
    """Return the first decoded FIT message of a given type as a dictionary."""
    return next(
        (extract_record(message) for message in fitfile.get_messages(message_name)),
        {},
    )


def build_workout_metadata(fitfile, records, bucket_name, file_name, workout_id):
    """Build a single, consistently typed row describing a workout."""
    sessions = [
        extract_record(message) for message in fitfile.get_messages("session")
    ]
    print(f"FIT sessions for {file_name}: {sessions}")
    session = sessions[0] if sessions else {}
    file_id = first_message(fitfile, "file_id")
    metadata = {column: None for column in METADATA_DTYPES}
    metadata.update(
        workout_id=workout_id,
        source_bucket=bucket_name,
        source_file=file_name,
    )

    for field_name in SESSION_FIELDS:
        metadata[field_name] = session.get(field_name)

    metadata["end_time"] = session.get("timestamp")
    metadata["manufacturer"] = file_id.get("manufacturer")
    metadata["product"] = file_id.get("product_name", file_id.get("product"))
    metadata["serial_number"] = file_id.get("serial_number")
    metadata["device_created_at"] = file_id.get("time_created")

    temperatures = [
        record["temperature"]
        for record in records
        if isinstance(record.get("temperature"), Real)
    ]
    if temperatures:
        if metadata["avg_temperature"] is None:
            metadata["avg_temperature"] = sum(temperatures) / len(temperatures)
        metadata["min_temperature"] = min(temperatures)
        if metadata["max_temperature"] is None:
            metadata["max_temperature"] = max(temperatures)

    df = pd.DataFrame([metadata])
    for field_name, dtype in METADATA_DTYPES.items():
        if dtype.startswith("datetime64"):
            df[field_name] = pd.to_datetime(
                df[field_name], errors="coerce", utc=True
            ).astype(dtype)
        elif dtype == "float64":
            df[field_name] = pd.to_numeric(df[field_name], errors="coerce").astype(dtype)
        else:
            df[field_name] = df[field_name].astype(dtype)
    return df


def parquet_output_name(file_name):
    return re.sub(r"\.fit$", ".parquet", file_name, flags=re.IGNORECASE)


@functions_framework.cloud_event
def process_fit_file(cloud_event: CloudEvent):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    if not file_name.lower().endswith(".fit"):
        print(f"Skipping non-fit file: {file_name}")
        return

    print(f"Processing: {file_name}")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    file_content = bucket.blob(file_name).download_as_bytes()

    fitfile = fitparse.FitFile(io.BytesIO(file_content))
    records = [extract_record(record) for record in fitfile.get_messages("record")]
    workout_id = workout_id_for(bucket_name, file_name)

    records_df = build_records_dataframe(records, file_name, workout_id)
    print(
        f"Extracted {len(records_df)} time-series records for {file_name}; "
        f"columns: {list(records_df.columns)}"
    )

    metadata_df = build_workout_metadata(
        fitfile, records, bucket_name, file_name, workout_id
    )
    output_filename = parquet_output_name(file_name)
    local_data_path = os.path.join("/tmp", os.path.basename(output_filename))
    local_metadata_path = os.path.join("/tmp", f"metadata-{os.path.basename(output_filename)}")
    records_df.to_parquet(local_data_path, index=False)
    metadata_df.to_parquet(local_metadata_path, index=False)

    data_blob = bucket.blob(f"processed/data/{output_filename}")
    metadata_blob = bucket.blob(f"processed/metadata/{output_filename}")
    data_blob.upload_from_filename(local_data_path)
    metadata_blob.upload_from_filename(local_metadata_path)

    print(f"Successfully uploaded records: {data_blob.name}")
    print(f"Successfully uploaded metadata: {metadata_blob.name}")


print("Function is done, let's hope it worked!...")

