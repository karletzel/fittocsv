import unittest
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pyarrow.parquet as pq

from main import (
    build_workout_metadata,
    build_records_dataframe,
    enforce_field_dtypes,
    extract_record,
    normalize_fit_value,
    parquet_output_name,
    verify_data_parquet,
    workout_id_for,
)


class FakeFitFile:
    def __init__(self, messages):
        self.messages = messages

    def get_messages(self, name):
        return self.messages.get(name, [])


def message(**values):
    return [SimpleNamespace(name=name, value=value) for name, value in values.items()]


class FitExtractionTest(unittest.TestCase):
    def test_records_dataframe_preserves_time_series_rows(self):
        first = datetime(2026, 8, 15, 10, tzinfo=timezone.utc)
        second = datetime(2026, 8, 15, 10, 0, 1, tzinfo=timezone.utc)
        records = [
            {"timestamp": first, "heart_rate": 120.0, "power": 200.0},
            {"timestamp": second, "heart_rate": 121.0, "power": 210.0},
        ]

        df = build_records_dataframe(records, "incoming/run.fit", "workout-1")

        self.assertEqual(len(df), 2)
        self.assertEqual(df["timestamp"].tolist(), [first, second])
        self.assertEqual(df["power"].tolist(), [200.0, 210.0])
        self.assertTrue((df["workout_id"] == "workout-1").all())
        parquet = BytesIO()
        df.to_parquet(parquet, index=False)
        round_trip = pd.read_parquet(parquet)
        self.assertEqual(len(round_trip), 2)
        self.assertIn("timestamp", round_trip.columns)
        self.assertIn("power", round_trip.columns)

    def test_records_dataframe_rejects_missing_time_series(self):
        with self.assertRaisesRegex(ValueError, "No FIT record messages"):
            build_records_dataframe([], "incoming/run.fit", "workout-1")
        with self.assertRaisesRegex(ValueError, "no timestamps"):
            build_records_dataframe([{"heart_rate": 120.0}], "incoming/run.fit", "workout-1")

    def test_verify_data_parquet_checks_round_trip_row_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parquet_file = os.path.join(temp_dir, "records.parquet")
            pd.DataFrame({"timestamp": [1, 2], "power": [200, 210]}).to_parquet(
                parquet_file, index=False
            )
            verified = verify_data_parquet(parquet_file, 2)
            self.assertEqual(len(verified), 2)
            with self.assertRaisesRegex(ValueError, "row count does not match"):
                verify_data_parquet(parquet_file, 3)

    def test_numeric_values_always_become_float(self):
        self.assertIsInstance(normalize_fit_value(12), float)
        self.assertIsInstance(normalize_fit_value(12.5), float)
        self.assertEqual(normalize_fit_value(Decimal("12.5")), 12.5)

    def test_bool_none_and_timestamp_keep_their_types(self):
        timestamp = datetime(2026, 8, 15, tzinfo=timezone.utc)
        self.assertIs(normalize_fit_value(True), True)
        self.assertIsNone(normalize_fit_value(None))
        self.assertIs(normalize_fit_value(timestamp), timestamp)

    def test_extract_record_normalizes_each_field(self):
        extracted = extract_record(message(power=250, speed=10.25, sport="cycling"))
        self.assertEqual(extracted, {"power": 250.0, "speed": 10.25, "sport": "cycling"})

    def test_heart_rate_has_double_parquet_type_for_integer_input(self):
        df = enforce_field_dtypes(pd.DataFrame({"heart_rate": [120, 121]}))
        parquet = BytesIO()
        df.to_parquet(parquet, index=False)
        self.assertEqual(str(pq.read_schema(parquet).field("heart_rate").type), "double")

    def test_heart_rate_has_float_type_when_all_values_are_null(self):
        df = enforce_field_dtypes(pd.DataFrame({"heart_rate": [None, None]}))
        self.assertEqual(str(df.dtypes["heart_rate"]), "float64")

    def test_metadata_extracts_session_device_and_temperature(self):
        start = datetime(2026, 8, 15, 10, tzinfo=timezone.utc)
        end = datetime(2026, 8, 15, 11, tzinfo=timezone.utc)
        fitfile = FakeFitFile({
            "session": [message(sport="running", sub_sport="trail", start_time=start,
                                timestamp=end, total_distance=10000, total_calories=700)],
            "file_id": [message(manufacturer="garmin", product_name="Forerunner",
                                serial_number=1234, time_created=start)],
        })
        records = [{"temperature": 10.0}, {"temperature": 14.0}]
        df = build_workout_metadata(fitfile, records, "fitness", "in/run.fit", "abc")

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "sport"], "running")
        self.assertEqual(df.loc[0, "sub_sport"], "trail")
        self.assertEqual(df.loc[0, "source_file"], "in/run.fit")
        self.assertEqual(df.loc[0, "avg_temperature"], 12.0)
        self.assertEqual(df.loc[0, "min_temperature"], 10.0)
        self.assertEqual(df.loc[0, "max_temperature"], 14.0)
        self.assertEqual(str(df.dtypes["total_distance"]), "float64")
        self.assertEqual(str(df.dtypes["start_time"]), "datetime64[ns, UTC]")

    def test_workout_id_is_stable_and_output_name_is_case_insensitive(self):
        self.assertEqual(workout_id_for("b", "x.fit"), workout_id_for("b", "x.fit"))
        self.assertNotEqual(workout_id_for("b", "x.fit"), workout_id_for("b", "y.fit"))
        self.assertEqual(parquet_output_name("folder/RUN.FIT"), "folder/RUN.parquet")


if __name__ == "__main__":
    unittest.main()

