"""Tests for de_toolbox.connectors.workday — call_wd_api, get_wd_dates, get_wd_wid."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from de_toolbox.connectors.workday import call_wd_api, get_wd_dates, get_wd_wid


class TestCallWdApi:
    @patch("de_toolbox.connectors.workday.requests.get")
    def test_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_get.return_value = mock_response

        result = call_wd_api("test_token", "https://api.workday.com/report")

        mock_get.assert_called_once_with(
            "https://api.workday.com/report",
            headers={"Authorization": "Bearer test_token"},
        )
        assert result == mock_response

    @patch("de_toolbox.connectors.workday.requests.get")
    def test_failure_raises(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="status code 401"):
            call_wd_api("bad_token", "https://api.workday.com/report")

    @patch("de_toolbox.connectors.workday.requests.get")
    def test_406_raises(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 406
        mock_response.text = "Data too large"
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="status code 406"):
            call_wd_api("token", "https://api.workday.com/report")


class TestGetWdDates:
    def _make_mock_row(self, calendar_date):
        """Create a mock Row returned by spark.sql().collect()[0].asDict()."""
        return {
            "CalendarDate": calendar_date,
            "CalendarYear": calendar_date.year,
            "FiscalYear": calendar_date.year
            if calendar_date.month >= 4
            else calendar_date.year - 1,
        }

    @patch("de_toolbox.connectors.workday.spark")
    def test_fiscal_month_after_april(self, mock_spark):
        cal_date = date(2025, 7, 15)
        row_data = self._make_mock_row(cal_date)

        mock_row = MagicMock()
        mock_row.asDict.return_value = row_data
        mock_spark.sql.return_value.collect.return_value = [mock_row]

        result = get_wd_dates("2025-07-15")

        assert result["FiscalMonth"] == 4  # July (7) - 3 = 4
        assert result["PastFiscalYear"] == row_data["FiscalYear"] - 1
        assert result["FiscalStart"] == date(row_data["FiscalYear"], 4, 1)
        assert result["FiscalEnd"] == date(row_data["FiscalYear"] + 1, 3, 31)

    @patch("de_toolbox.connectors.workday.spark")
    def test_fiscal_month_before_april(self, mock_spark):
        cal_date = date(2025, 2, 10)
        row_data = self._make_mock_row(cal_date)

        mock_row = MagicMock()
        mock_row.asDict.return_value = row_data
        mock_spark.sql.return_value.collect.return_value = [mock_row]

        result = get_wd_dates("2025-02-10")

        assert result["FiscalMonth"] == 11  # Feb (2) + 9 = 11

    @patch("de_toolbox.connectors.workday.spark")
    def test_april_boundary(self, mock_spark):
        cal_date = date(2025, 4, 1)
        row_data = self._make_mock_row(cal_date)

        mock_row = MagicMock()
        mock_row.asDict.return_value = row_data
        mock_spark.sql.return_value.collect.return_value = [mock_row]

        result = get_wd_dates("2025-04-01")

        assert result["FiscalMonth"] == 1  # April (4) - 3 = 1

    @patch("de_toolbox.connectors.workday.spark")
    def test_past_dates_computed(self, mock_spark):
        cal_date = date(2025, 6, 15)
        row_data = self._make_mock_row(cal_date)

        mock_row = MagicMock()
        mock_row.asDict.return_value = row_data
        mock_spark.sql.return_value.collect.return_value = [mock_row]

        result = get_wd_dates("2025-06-15")

        assert result["PastCalendarYear"] == 2024
        assert result["PastYearDate"] == date(2024, 6, 15)
        assert result["PastMonthDate"] == date(2025, 5, 15)
        assert result["PastMonthStart"] == date(2025, 5, 1)
        assert result["PastMonthEnd"] == date(2025, 5, 31)
        assert result["Past2MonthStart"] == date(2025, 4, 1)
        assert result["MonthEnd"] == date(2025, 6, 30)


class TestGetWdWid:
    @patch("de_toolbox.connectors.workday.spark")
    def test_year_type(self, mock_spark):
        report_date = {
            "CalendarYear": 2025,
            "PastCalendarYear": 2024,
        }

        mock_spark.sql.return_value.collect.side_effect = [
            [["WID_2024"]],
            [["WID_2025"]],
        ]

        result = get_wd_wid("year", report_date)

        assert result.startswith("&Year%21WID=")
        assert "WID_2024" in result
        assert "WID_2025" in result
        assert "!" in result

    @patch("de_toolbox.connectors.workday.spark")
    def test_period_type(self, mock_spark):
        report_date = {
            "FiscalYear": 2025,
            "FiscalMonth": 3,
        }

        mock_spark.sql.return_value.collect.side_effect = [
            [["WID_P1"]],
            [["WID_P2"]],
            [["WID_P3"]],
        ]

        result = get_wd_wid("period", report_date)

        assert result.startswith("&Period%21WID=")
        assert "WID_P1" in result
        assert "WID_P2" in result
        assert "WID_P3" in result
        assert not result.endswith("!")
