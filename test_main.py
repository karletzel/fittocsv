import unittest
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pyarrow.parquet as pq

from main import enforce_field_dtypes, extract_record, normalize_fit_value


class NormalizeFitValueTest(unittest.TestCase):
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
        record = [
            SimpleNamespace(name="power", value=250),
            SimpleNamespace(name="speed", value=10.25),
            SimpleNamespace(name="sport", value="cycling"),
        ]

        extracted = extract_record(record)

        self.assertEqual(
            extracted,
            {"power": 250.0, "speed": 10.25, "sport": "cycling"},
        )
        self.assertIsInstance(extracted["power"], float)
        self.assertIsInstance(extracted["speed"], float)

    def test_heart_rate_has_double_parquet_type_for_integer_input(self):
        df = enforce_field_dtypes(pd.DataFrame({"heart_rate": [120, 121]}))
        parquet = BytesIO()

        df.to_parquet(parquet, index=False)

        self.assertEqual(str(df.dtypes["heart_rate"]), "float64")
        self.assertEqual(str(pq.read_schema(parquet).field("heart_rate").type), "double")

    def test_heart_rate_has_float_type_when_all_values_are_null(self):
        df = enforce_field_dtypes(pd.DataFrame({"heart_rate": [None, None]}))

        self.assertEqual(str(df.dtypes["heart_rate"]), "float64")


if __name__ == "__main__":
    unittest.main()
