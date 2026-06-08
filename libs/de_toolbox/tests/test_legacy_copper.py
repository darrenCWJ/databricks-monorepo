"""Tests for de_toolbox._legacy.copper_excel_csv — ported from test_copper.py."""

import pandas as pd
from de_toolbox._legacy.copper_excel_csv import (
    check_columns,
    check_file_name_convention,
    check_file_type,
    clean_and_title_column_names,
    concat_dict_dataframes,
    convert_path,
    ms_to_formatted_date,
)


class TestCheckColumns:
    def setup_method(self):
        self.df = pd.DataFrame(columns=["A", "B", "C", "D"])
        self.known_columns = ["A", "B", "C", "D"]

    def test_matching_columns(self):
        assert check_columns(self.df, self.known_columns)

    def test_mismatched_columns(self):
        df_mismatched = pd.DataFrame(columns=["A", "B", "C", "E"])
        assert not check_columns(df_mismatched, self.known_columns)

    def test_extra_column_in_df(self):
        df_extra = pd.DataFrame(columns=["A", "B", "C", "D", "E"])
        assert not check_columns(df_extra, self.known_columns)

    def test_missing_column_in_df(self):
        df_missing = pd.DataFrame(columns=["A", "B", "C"])
        assert not check_columns(df_missing, self.known_columns)

    def test_whitelist(self):
        df_whitelist = pd.DataFrame(columns=["A", "B", "C", "D", "E"])
        assert check_columns(df_whitelist, self.known_columns, whitelist=["E"])

    def test_whitelist_missing_column(self):
        df_whitelist_missing = pd.DataFrame(columns=["A", "B", "C"])
        assert check_columns(df_whitelist_missing, self.known_columns, whitelist=["D"])

    def test_case_sensitivity(self):
        df_case = pd.DataFrame(columns=["a", "B", "c", "D"])
        assert not check_columns(df_case, self.known_columns)


class TestCheckFileType:
    def test_csv_file(self):
        assert check_file_type("file.csv", "csv")
        assert check_file_type("file.CSV", "csv")
        assert not check_file_type("file.txt", "csv")

    def test_excel_file(self):
        assert check_file_type("file.xls", "excel")
        assert check_file_type("file.xlsx", "excel")
        assert check_file_type("file.xlsm", "excel")
        assert not check_file_type("file.csv", "excel")

    def test_json_file(self):
        assert check_file_type("file.json", "json")
        assert not check_file_type("file.txt", "json")

    def test_parquet_file(self):
        assert check_file_type("file.parquet", "parquet")
        assert not check_file_type("file.csv", "parquet")

    def test_avro_file(self):
        assert check_file_type("file.avro", "avro")
        assert not check_file_type("file.txt", "avro")

    def test_unsupported_file_type(self):
        assert not check_file_type("file.txt", "txt")
        assert not check_file_type("file.pdf", "pdf")

    def test_case_insensitivity(self):
        assert check_file_type("file.CSV", "csv")
        assert check_file_type("file.csv", "CSV")
        assert check_file_type("file.XLSX", "excel")

    def test_full_path(self):
        assert check_file_type("/path/to/file.csv", "csv")
        assert check_file_type("C:\\Users\\file.xlsx", "excel")


class TestCheckFileNameConvention:
    def test_matching_file_name(self):
        assert check_file_name_convention("data_2023-01-01.csv", r"data_\d{4}-\d{2}-\d{2}")
        assert check_file_name_convention("/path/to/log_file_001.txt", r"log_file_\d{3}")

    def test_non_matching_file_name(self):
        assert not check_file_name_convention("data_2023-01-01.csv", r"log_\d{4}-\d{2}-\d{2}")
        assert not check_file_name_convention("invalid_name.txt", r"valid_name_\d+")

    def test_case_sensitivity(self):
        assert check_file_name_convention("DATA_001.csv", r"DATA_\d{3}")
        assert not check_file_name_convention("data_001.csv", r"DATA_\d{3}")

    def test_empty_file_name(self):
        assert not check_file_name_convention("", r"\w+")

    def test_invalid_regex(self):
        assert not check_file_name_convention("file.txt", r"[")


class TestCleanAndTitleColumnNames:
    def test_basic_cleaning(self):
        input_columns = ["first name", "last_name", "email address"]
        expected_output = ["FirstName", "LastName", "EmailAddress"]
        assert clean_and_title_column_names(input_columns) == expected_output

    def test_remove_special_characters(self):
        input_columns = ["user@id", "phone#number", "address\!"]
        expected_output = ["UserId", "PhoneNumber", "Address"]
        assert clean_and_title_column_names(input_columns) == expected_output

    def test_preserve_numbers(self):
        input_columns = ["column1", "column2", "column3"]
        expected_output = ["Column1", "Column2", "Column3"]
        assert clean_and_title_column_names(input_columns) == expected_output


class TestConcatDictDataframes:
    def test_basic_concatenation(self):
        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"A": [5, 6], "B": [7, 8]})
        df_dict = {"df1": df1, "df2": df2}

        expected_result = pd.DataFrame({"A": [1, 2, 5, 6], "B": [3, 4, 7, 8]})
        result = concat_dict_dataframes(df_dict)

        pd.testing.assert_frame_equal(result, expected_result)

    def test_single_dataframe(self):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df_dict = {"df": df}

        result = concat_dict_dataframes(df_dict)
        pd.testing.assert_frame_equal(result, df)


class TestMsToFormattedDate:
    def test_basic_conversion(self):
        timestamp_ms = 1609459200000
        format_string = "%Y-%m-%d %H:%M:%S"
        expected_output = "2021-01-01 00:00:00"
        assert ms_to_formatted_date(timestamp_ms, format_string) == expected_output

    def test_different_format(self):
        timestamp_ms = 1609459200000
        format_string = "%d/%m/%Y"
        expected_output = "01/01/2021"
        assert ms_to_formatted_date(timestamp_ms, format_string) == expected_output

    def test_large_timestamp(self):
        timestamp_ms = 32503680000000
        format_string = "%Y"
        expected_output = "3000"
        assert ms_to_formatted_date(timestamp_ms, format_string) == expected_output


class TestConvertPath:
    def setup_method(self):
        self.source_base_path = "/source/data"
        self.target_base_path = "/target/data"

    def test_basic_conversion(self):
        source_file = "/source/data/file.txt"
        expected = "/target/data/file.txt"
        result = convert_path(source_file, self.source_base_path, self.target_base_path, {})
        assert result == expected

    def test_nested_directory(self):
        source_file = "/source/data/subdir/file.txt"
        expected = "/target/data/subdir/file.txt"
        result = convert_path(source_file, self.source_base_path, self.target_base_path, {})
        assert result == expected

    def test_csv_to_parquet(self):
        source_file = "/source/data/file.csv"
        expected = "/target/data/file.parquet"
        result = convert_path(
            source_file, self.source_base_path, self.target_base_path, {"file_type": "csv"}
        )
        assert result == expected

    def test_excel_to_parquet(self):
        source_file = "/source/data/file.xlsx"
        expected = "/target/data/file.parquet"
        result = convert_path(
            source_file, self.source_base_path, self.target_base_path, {"file_type": "excel"}
        )
        assert result == expected

    def test_other_file_type_no_change(self):
        source_file = "/source/data/file.json"
        expected = "/target/data/file.json"
        result = convert_path(
            source_file, self.source_base_path, self.target_base_path, {"file_type": "json"}
        )
        assert result == expected
