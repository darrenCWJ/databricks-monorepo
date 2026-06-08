from datetime import date, datetime, timedelta

import requests
from databricks.sdk.runtime import spark
from dateutil.relativedelta import relativedelta


def call_wd_api(token, api_url):
    # Insert access token into headers
    custom_headers = {"Authorization": "Bearer " + token}

    # Error 401 may be due to not having https:// in the api
    # Error 406 is caused by large data volume, reduce date range
    response = requests.get(api_url, headers=custom_headers)
    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        raise Exception(f"API request failed with status code {response.status_code}")

    return response


def get_wd_dates(report_date=""):
    if report_date == "":
        report_date = datetime.now() + timedelta(hours=8) - timedelta(days=1)
        report_date = report_date.strftime("%Y-%m-%d")
    report_date = (
        spark.sql(f"SELECT * FROM common.calendar.dim_dates WHERE CalendarDate = '{report_date}'")
        .collect()[0]
        .asDict()
    )

    # not recommended to use custom dates for backfill
    # the PastXXX logic needs detailed testing
    if report_date["CalendarDate"].month >= 4:
        report_date["FiscalMonth"] = report_date["CalendarDate"].month - 3
    else:
        report_date["FiscalMonth"] = report_date["CalendarDate"].month + 9
    report_date["PastFiscalYear"] = report_date["FiscalYear"] - 1
    report_date["FiscalStart"] = date(report_date["FiscalYear"], 4, 1)
    report_date["FiscalEnd"] = date(report_date["FiscalYear"] + 1, 3, 31)
    report_date["MonthEnd"] = (report_date["CalendarDate"] + relativedelta(months=1)).replace(
        day=1
    ) - relativedelta(days=1)
    report_date["PastCalendarYear"] = report_date["CalendarYear"] - 1
    report_date["PastYearDate"] = report_date["CalendarDate"] - relativedelta(years=1)
    report_date["PastMonthDate"] = report_date["CalendarDate"] - relativedelta(months=1)
    report_date["PastMonthStart"] = report_date["PastMonthDate"].replace(day=1)
    report_date["PastMonthEnd"] = report_date["CalendarDate"].replace(day=1) - relativedelta(days=1)
    report_date["Past2MonthStart"] = (
        report_date["CalendarDate"] - relativedelta(months=2)
    ).replace(day=1)

    return report_date


def get_wd_wid(type, report_date):
    # Used in FIN-dtl APIs
    # Calculates the current and past year WIDs
    if type == "year":
        wid = "&Year%21WID="
        current_year = str(report_date["CalendarYear"])
        past_year = str(report_date["PastCalendarYear"])

        wid += spark.sql(
            f"SELECT WID FROM common.calendar.wd_wid_year WHERE CalendarYear = '{past_year}'"
        ).collect()[0][0]
        wid += (
            "!"
            + spark.sql(
                f"SELECT WID FROM common.calendar.wd_wid_year WHERE CalendarYear = '{current_year}'"
            ).collect()[0][0]
        )

    # Used in FIN-rar API
    # Calculates the WIDs for each month in the current FY up till current month
    elif type == "period":
        wid = "&Period%21WID="
        for i in range(report_date["FiscalMonth"]):
            period = str(report_date["FiscalYear"]) + "-P" + str(i + 1)
            wid += (
                spark.sql(
                    f"SELECT WID FROM common.calendar.wd_wid_period WHERE WorkdayPeriod = '{period}'"
                ).collect()[0][0]
                + "!"
            )
        wid = wid[:-1]

    return wid
