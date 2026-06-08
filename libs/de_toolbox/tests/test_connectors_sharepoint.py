"""Tests for de_toolbox.connectors.sharepoint — ported from test_sharepoint.py."""

from unittest.mock import Mock, patch

import pandas as pd
import pytest
from de_toolbox._legacy.sharepoint_v1 import (
    clean_path,
    create_sharepoint_session,
    get_all_lists,
    get_first_path_element,
    save_pandas_df_to_volume,
)


class TestCreateSharepointSession:
    @patch("de_toolbox._legacy.sharepoint_v1.requests.Session")
    @patch("de_toolbox._legacy.sharepoint_v1.HttpNtlmAuth")
    def test_create_sharepoint_session(self, mock_http_ntlm_auth, mock_session):
        username = "test_user"
        password = "test_password"
        ca_cert_path = "/path/to/ca_cert.pem"

        mock_session_instance = mock_session.return_value

        result = create_sharepoint_session(username, password, ca_cert_path)

        mock_session.assert_called_once()
        mock_http_ntlm_auth.assert_called_once_with(username, password)
        assert mock_session_instance.auth == mock_http_ntlm_auth.return_value
        assert mock_session_instance.verify == ca_cert_path
        assert result == mock_session_instance


class TestGetAllLists:
    def setup_method(self):
        self.mock_session = Mock()
        self.url = "https://example.sharepoint.com/sites/testsite"

    def test_get_all_lists_success(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "d": {"results": [{"Title": "List 1"}, {"Title": "List 2"}, {"Title": "List 3"}]}
        }
        self.mock_session.get.return_value = mock_response

        result = get_all_lists(self.mock_session, self.url)

        assert result == ["List 1", "List 2", "List 3"]

    def test_get_all_lists_failure(self):
        mock_response = Mock()
        mock_response.status_code = 404
        self.mock_session.get.return_value = mock_response

        with patch("builtins.print"):
            result = get_all_lists(self.mock_session, self.url)

        assert result == []


class TestCleanPath:
    def test_clean_path(self):
        test_cases = [
            ("  //some/path//  ", "some/path"),
            ("//another/path//", "another/path"),
            ("no//backslashes", "no//backslashes"),
            ("////double////backslashes////", "double////backslashes"),
            ("", ""),
            ("//", ""),
            ("  //  ", ""),
            ("/path/with/single/slashes/", "path/with/single/slashes"),
            (
                "  path/with/no/leading/or/trailing/slashes  ",
                "path/with/no/leading/or/trailing/slashes",
            ),
        ]
        for input_path, expected_output in test_cases:
            assert clean_path(input_path) == expected_output

    def test_clean_path_with_non_string_input(self):
        with pytest.raises(AttributeError):
            clean_path(123)


class TestGetFirstPathElement:
    def test_get_first_path_element(self):
        test_cases = [
            ("/Users/Username/Documents", "Users"),
            ("//NetworkShare/Folder/File.txt", "NetworkShare"),
            ("Folder/Subfolder/File.txt", "Folder"),
            ("/Folder/File.txt", "Folder"),
            ("///", ""),
            ("", ""),
            ("/", ""),
            ("File.txt", "File.txt"),
            ("usr/local/bin", "usr"),
            ("/etc/config", "etc"),
            ("~/Documents", "~"),
        ]
        for input_path, expected_output in test_cases:
            assert get_first_path_element(input_path) == expected_output


class TestSavePandasDfToVolume:
    @patch("pandas.DataFrame.to_parquet")
    @patch("builtins.print")
    def test_save_pandas_df_to_volume(self, mock_print, mock_to_parquet):
        mock_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        volume_path = "/mnt/data"
        file_name = "test_file"

        save_pandas_df_to_volume(mock_df, volume_path, file_name)

        expected_path = "/mnt/data/test_file.parquet"
        mock_to_parquet.assert_called_once_with(expected_path, index=False)
        mock_print.assert_called_once_with(f"Files saved to {expected_path}")
