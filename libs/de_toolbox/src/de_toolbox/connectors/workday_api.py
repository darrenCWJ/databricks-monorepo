import os
from datetime import date, datetime, timedelta

import urllib3
from botocore.config import Config
from dateutil.relativedelta import relativedelta
from urllib3._collections import HTTPHeaderDict


def workday_api(event, token, volume):
    status = "Completed"
    my_config = Config(read_timeout=900)
    now = datetime.now() + timedelta(hours=8)
    tokenid = "Bearer " + token

    # retrieve compulsory parameters from json
    print(event)
    directory = event["directory"]
    source_name = event["source_name"]
    api_url = event["api_url"]
    # get all universal variables ready
    additional_parameters = ""
    yesterday = now.date() - timedelta(days=1)
    month = int(yesterday.month)
    year = int(yesterday.year)
    current_day = yesterday.strftime("%Y%m%d")

    if event["current_day"] != "":
        current_day = event["current_day"]
        yesterday = datetime.strptime(current_day, "%Y-%m-%d").date()
        month = int(yesterday.month)
        year = int(yesterday.year)

    if month < 4:
        last_fy = year - 2
    else:
        last_fy = year - 1

    headers = HTTPHeaderDict()
    headers.add("Authorization", tokenid)
    headers.add("Connection", "keep-alive")
    # print(tokenid)
    # print(headers)

    ###this segment is specially for dtl and dtl adjustments
    ###IE everyday from apr 2025 to mar 2026, i will keep refreshing feb-mar 2025 figures
    if source_name == "dtlsa":
        extra_name = "_adjustment" + str(yesterday.month) + str(yesterday.day)
        source_name = "dtls"
        # changing the date to 31/3 of the current financial year
        if month < 4:
            year -= 1
        yesterday = date(year, 3, 31)
        month = int(yesterday.month)
        current_day = yesterday.strftime("%Y%m%d")
    elif source_name == "dtla":
        extra_name = "_adjustment" + str(yesterday.month) + str(yesterday.day)
        source_name = "dtl"
        # changing the date to 31/3 of the year
        if month < 4:
            year -= 1
        yesterday = date(year, 3, 31)
        month = int(yesterday.month)
        current_day = yesterday.strftime("%Y%m%d")
    else:
        extra_name = ""

    match source_name:
        # FIN cases
        case "dtlm":
            """the logic for from date is the beginning of 2 months ago 
          and the to is till yesterday
          so for example, if i run today(24/1/2024), it will be from 1st Nov to 23rd Jan
          if i run on 2nd Feb, it will be from 1st Dec to 1st Feb"""
            year_for_two_month_ago = year
            two_month_ago = month - 2
            if two_month_ago <= 0:
                year_for_two_month_ago = year - 1
                two_month_ago += 12
            first_day_of_last_month = date(year_for_two_month_ago, (two_month_ago), 1)
            year_WID = wd_year_lookup({"year": year, "month": month})
            additional_parameters = (
                f"&Accounting_Date_From={str(first_day_of_last_month)}%2B08:00&Accounting_Date_To={str(yesterday)}%2B08:00"
                + year_WID
            )

        case "dtls":
            """the logic for from date is the beginning of 2 months ago 
          and the to is till yesterday
          so for example, if i run today(24/1/2024), it will be from 1st Nov to 23rd Jan
          if i run on 2nd Feb, it will be from 1st Dec to 1st Feb"""
            year_for_two_month_ago = year
            two_month_ago = month - 2
            if two_month_ago <= 0:
                year_for_two_month_ago = year - 1
                two_month_ago += 12
            first_day_of_last_month = date(year_for_two_month_ago, (two_month_ago), 1)
            year_WID = wd_year_lookup({"year": year, "month": month})
            additional_parameters = (
                f"&Accounting_Date_From={str(first_day_of_last_month)}%2B08:00&Accounting_Date_To={str(yesterday)}%2B08:00"
                + year_WID
            )

        case "dtl":
            """the logic for from date is the beginning of 2 months ago 
          and the to is till yesterday
          so for example, if i run today(24/1/2024), it will be from 1st Nov to 23rd Jan
          if i run on 2nd Feb, it will be from 1st Dec to 1st Feb"""
            year_for_two_month_ago = year
            two_month_ago = month - 2
            if two_month_ago <= 0:
                year_for_two_month_ago = year - 1
                two_month_ago += 12
            first_day_of_last_month = date(year_for_two_month_ago, (two_month_ago), 1)
            year_WID = wd_year_lookup({"year": year, "month": month})
            additional_parameters = (
                f"&Accounting_Date_From={str(first_day_of_last_month)}%2B08:00&Accounting_Date_To={str(yesterday)}%2B08:00"
                + year_WID
            )

        case "cdi":
            additional_parameters = f"&Invoice_Date_On_or_Before={yesterday}-07%3A00"

        case "rar":
            period_WID = wd_period_lookup({"year": year, "month": month})
            additional_parameters = period_WID

        case "poc":
            additional_parameters = (
                f"&Issued_on_or_After=2003-01-01&Document_Date_on_or_Before={yesterday}"
            )

        case "cri":
            if month > 3:
                start_of_fy_cycle = str(year) + "-04-01"
                end_of_fy_cycle = str(year + 1) + "-03-31"
            else:
                start_of_fy_cycle = str(year - 1) + "-04-01"
                end_of_fy_cycle = str(year) + "-03-31"
            additional_parameters = f"&Invoice_Accounting_Date_From={start_of_fy_cycle}%2B08:00&Invoice_Accounting_Date_To={end_of_fy_cycle}%2B08:00"

        case "fpr":
            start_of_last_month = str(date(year, month - 1, 1))
            first_day_of_the_month = date(year, month, 1)
            end_of_last_month = str(first_day_of_the_month - timedelta(days=1))
            additional_parameters = f"&Settlement_Date_From={start_of_last_month}%2B08:00&Settlement_Date_To={end_of_last_month}%2B08:00"

        # HCM cases
        case "mlr":
            additional_parameters = f"&Prompt_-_Date_1={str(yesterday)}%2B08%3A00&Effective_as_of_Date={str(yesterday)}-07%3A00&Prompt_-_Text_1={last_fy}"

        case "hpl":
            additional_parameters = f"&Effective_Date={str(yesterday)}-07%3A00"

        case "eqr":
            additional_parameters = f"Prompt_-_Date_1={str(yesterday)}-07%3A00&Effective_as_of_Date={str(yesterday)}-07%3A00&Prompt_-_Text_1={last_fy}"

        case "whr":
            """one_year_forward = now.date() + relativedelta(years=1)
          one_year_backward = now.date() - relativedelta(years=1)
          month_before = now.date() - relativedelta(months=1)
          first_day_of_last_month = month_before.replace(day=1)
          last_day_of_last_month = now.date().replace(day=1) - timedelta(days=1)
          additional_parameters=f"&Event_Effective_Date_On_or_After=2020-06-01-07%3A00"""
            # additional_parameters=f"&Event_Effective_Date_On_or_After={str(one_year_backward)}-07%3A00"
            # additional_parameters=f"&Event_Effective_Date_On_or_Before={str(one_year_forward)}-07%3A00&Event_Effective_Date_On_or_After={str(one_year_backward)}-07%3A00&Completed_Date_On_or_Before={str(last_day_of_last_month)}T00%3A00%3A00.000-08%3A00&Completed_Date_On_or_After={str(first_day_of_last_month)}T00%3A00%3A00.000-08%3A00"
            pass

        case "wdr":
            last_day_of_last_month = now.date().replace(day=1) - timedelta(days=1)
            last_year = year - 1
            additional_parameters = f"&Effective_Date={str(yesterday)}-08%3A00&Prompt_-_Date_1={str(last_day_of_last_month)}-07%3A00&Effective_as_of_Date={str(yesterday)}-07%3A00&Prompt_-_Text_1={last_year}"

        case "eso":
            additional_parameters = f"&Effective_as_of_Date={str(yesterday)}%2B08:00"

        case "tdoe":
            one_year_backward = now.date() - relativedelta(years=1)
            additional_parameters = f"&Most_Recent_Performance_Review_Year={last_fy}&Effective_Date__Length_of_Service_={str(yesterday)}-07%3A00&To_Termination_Date={str(yesterday)}-07%3A00&From_Termination_Date={str(one_year_backward)}-07%3A00"

        case "wmr":
            month_before = yesterday - relativedelta(months=1)
            additional_parameters = f"&Completed_Date_On_or_Before={str(yesterday)}T00:00:00.000%2B08:00&Completed_Date_On_or_After={month_before}T00:00:00.000%2B08:00"

    # print(f"additional_parameters is {additional_parameters}")

    api_url = api_url + additional_parameters
    print(api_url)

    http = urllib3.PoolManager()
    timeout = urllib3.Timeout(connect=900, read=900)
    current_day = current_day.replace("-", "")

    webpage = http.request("GET", api_url, headers=headers, timeout=timeout)
    print("request ran")

    Body = webpage.data.decode("utf-8")
    csvdata2 = Body.splitlines()
    length = len(csvdata2)
    if webpage.status != 200:
        print(f"webpage.status is {webpage.status}")
        print("401 is incorrect username password. probably due to not having https:// in the api")
        print("406 is too large data volume. try putting in from/to date parameters to reduce data")
        raise ConnectionError("webpage status is not 200")
    elif "<!DOCTYPE html>" in csvdata2:
        raise ConnectionError("bad response from api")
    elif length < 2:
        print(Body)
        print("There's no data")
        print("not putting content to s3")
    else:
        print("putting content to volume")
        filename = directory[3:] + "_" + current_day + ".csv"
        file_path = os.path.join(volume, directory, filename)
        # if not os.path.isdir(directory):
        #    os.mkdir(directory)
        with open(file_path, "w") as file:
            file.write(Body)
        print("Put content to volume done")


def wd_year_lookup(event):
    month = int(event["month"])
    year1 = int(event["year"])
    str_year1 = str(year1)
    year2 = year1 - 1
    str_year2 = str(year2)
    table = {
        "2016": "27bc56da9e6a01ead892f3eaac078972",
        "2017": "27bc56da9e6a01a8898cfbeaac079672",
        "2018": "27bc56da9e6a013abce902ebac07a372",
        "2019": "27bc56da9e6a0159bc1f0aebac07b072",
        "2020": "27bc56da9e6a010ff9c110ebac07bd72",
        "2021": "27bc56da9e6a019d1d9917ebac07ca72",
        "2022": "27bc56da9e6a01bb77551eebac07d772",
        "2023": "27bc56da9e6a0194d20b25ebac07e472",
        "2024": "27bc56da9e6a0120bd642bebac07f172",
        "2025": "27bc56da9e6a0197c26232ebac07fe72",
        "2026": "27bc56da9e6a010a634839ebac070b73",
        "2027": "27bc56da9e6a0171ea5a40ebac071873",
        "2028": "27bc56da9e6a01d7821947ebac072573",
        "2029": "27bc56da9e6a018ac9654eebac073273",
        "2030": "27bc56da9e6a01acc26755ebac073f73",
        "2015": "7ef48c7d7227016a6dbd6788670ed36b",
        "2014": "7ef48c7d7227018ff03d708b670e506c",
        "2013": "7ef48c7d72270184d8337c8e670ecc6c",
        "2012": "7ef48c7d7227016f01951193670e5b6d",
        "2011": "7ef48c7d7227013ecca58d95670ec46d",
        "2010": "7ef48c7d72270126ddba8e99670e216e",
        "2009": "7ef48c7d7227015c304c519c670e8a6e",
        "2008": "7ef48c7d72270148fd14ec9e670ec76e",
        "2007": "7ef48c7d72270141878df6a1670e336f",
        "2006": "7ef48c7d722701d8d212baa4670e9c6f",
        "2005": "7ef48c7d7227018f9f59e2a7670ed56f",
        "2004": "7ef48c7d7227015ff1dbbb697c0ea6b6",
        "2031": "ec0069951130012086286c1c3a06bc17",
        "2032": "e717b61cab5d01f04f6071dbfb007621",
        "2034": "e717b61cab5d015d8492b1e7fb008521",
        "2037": "e717b61cab5d015c94ed6850ef0198d5",
        "2040": "e717b61cab5d010d614b0759ef01b0d5",
        "2033": "54132840953801c29433d9e3fb003c21",
        "2035": "54132840953801e93deb6943ef01c0e0",
        "2036": "6768bef0a2950172a49c5d4fef01f0c7",
        "2039": "6768bef0a29501cb8cec0357ef011ec8",
        "2038": "377d9401bc73019863b63653ef0107bf",
        "2003": "ec6aaccdf643015aaeba18cbcc01cb71",
        "2002": "ec6aaccdf643019008c609cfcc01d871",
        "2000": "ec6aaccdf64301389ec5b1d6cc01e571",
        "2001": "7f360f7ecd5a014730b79bd3cc013b7a",
        "1999": "7f360f7ecd5a01332cd1ffd9cc01537a",
        "1996": "7f360f7ecd5a01f791d59ee4cc01607a",
        "1995": "7f360f7ecd5a01695bb41b6fd0018e7a",
        "1994": "7f360f7ecd5a016dd589a071d0019b7a",
        "1998": "fd739034dda30109bcf73ddccc019a78",
        "1997": "d4692729218f0174eb961ee0cc01bc79",
        "2041": "11c51efb63551000e04779459bd00000",
        "2042": "24156fb7f9d01000e04d57c9ac0a0000",
        "2043": "ba1d864aefb61000e05600f60d900000",
        "2044": "91629137d4eb1001c015a1a9c9110000",
        "2045": "91629137d4eb1001c019b959c5ef0000",
        "2046": "5350f41bb8051001c01fdb7c107c0000",
        "2047": "449c5c3bd8f71001c02221692c390000",
        "2048": "449c5c3bd8f71001c024fce959eb0000",
        "2049": "ba6ad33f40121001c027880c16ae0000",
        "2050": "f3a4c5aa2f081001c02a8d80bada0000",
    }
    WID1 = table[str_year1]
    WID2 = table[str_year2]
    WID_year = "&Year%21WID=" + WID1 + "!" + WID2

    print(WID_year)
    return WID_year


def wd_period_lookup(event):
    month = int(event["month"])
    year = int(event["year"])
    if month < 4:
        year -= 1
    period = month - 3
    if period <= 0:
        period += 12
    table = {
        "2016-P1 ": "27bc56da9e6a01cdb61cf4eaac078a72",
        "2016-P2 ": "27bc56da9e6a01bca747f4eaac078b72",
        "2016-P3 ": "27bc56da9e6a017eac90f4eaac078c72",
        "2016-P4 ": "27bc56da9e6a01400198f4eaac078d72",
        "2016-P5 ": "27bc56da9e6a012ee19ef4eaac078e72",
        "2016-P6 ": "27bc56da9e6a016f92a5f4eaac078f72",
        "2016-P7 ": "27bc56da9e6a017ed1acf4eaac079072",
        "2016-P8 ": "27bc56da9e6a015d08b4f4eaac079172",
        "2016-P9 ": "27bc56da9e6a01c2d0bbf4eaac079272",
        "2016-P10": "27bc56da9e6a01fa98c3f4eaac079372",
        "2016-P11": "27bc56da9e6a01bbcc1af5eaac079472",
        "2016-P12": "27bc56da9e6a01d17325f5eaac079572",
        "2017-P1 ": "27bc56da9e6a018ed8e9fbeaac079772",
        "2017-P2 ": "27bc56da9e6a0188220bfceaac079872",
        "2017-P3 ": "27bc56da9e6a012a0212fceaac079972",
        "2017-P4 ": "27bc56da9e6a01bdb718fceaac079a72",
        "2017-P5 ": "27bc56da9e6a0140ca1ffceaac079b72",
        "2017-P6 ": "27bc56da9e6a012eb726fceaac079c72",
        "2017-P7 ": "27bc56da9e6a019e3a2efceaac079d72",
        "2017-P8 ": "27bc56da9e6a01d3b335fceaac079e72",
        "2017-P9 ": "27bc56da9e6a01a9799ffceaac079f72",
        "2017-P10": "27bc56da9e6a01229da8fceaac07a072",
        "2017-P11": "27bc56da9e6a01fe35b1fceaac07a172",
        "2017-P12": "27bc56da9e6a014949bafceaac07a272",
        "2018-P1 ": "27bc56da9e6a014acafc02ebac07a472",
        "2018-P2 ": "27bc56da9e6a0155020c03ebac07a572",
        "2018-P3 ": "27bc56da9e6a011eee1103ebac07a672",
        "2018-P4 ": "27bc56da9e6a0141381803ebac07a772",
        "2018-P5 ": "27bc56da9e6a0184741e03ebac07a872",
        "2018-P6 ": "27bc56da9e6a01ace32403ebac07a972",
        "2018-P7 ": "27bc56da9e6a01cc378a03ebac07aa72",
        "2018-P8 ": "27bc56da9e6a01d0b29203ebac07ab72",
        "2018-P9 ": "27bc56da9e6a01d3469a03ebac07ac72",
        "2018-P10": "27bc56da9e6a01f54fa203ebac07ad72",
        "2018-P11": "27bc56da9e6a01654daa03ebac07ae72",
        "2018-P12": "27bc56da9e6a01320db303ebac07af72",
        "2019-P1 ": "27bc56da9e6a01813e330aebac07b172",
        "2019-P2 ": "27bc56da9e6a01bf2c430aebac07b272",
        "2019-P3 ": "27bc56da9e6a01a037490aebac07b372",
        "2019-P4 ": "27bc56da9e6a012abb4f0aebac07b472",
        "2019-P5 ": "27bc56da9e6a01e384ae0aebac07b572",
        "2019-P6 ": "27bc56da9e6a01a1efb50aebac07b672",
        "2019-P7 ": "27bc56da9e6a01b178bd0aebac07b772",
        "2019-P8 ": "27bc56da9e6a0139d9c40aebac07b872",
        "2019-P9 ": "27bc56da9e6a01ebc7cc0aebac07b972",
        "2019-P10": "27bc56da9e6a0193cdd40aebac07ba72",
        "2019-P11": "27bc56da9e6a018086dd0aebac07bb72",
        "2019-P12": "27bc56da9e6a01ec71e60aebac07bc72",
        "2020-P1 ": "27bc56da9e6a014f9edb10ebac07be72",
        "2020-P2 ": "27bc56da9e6a011702ed10ebac07bf72",
        "2020-P3 ": "27bc56da9e6a01f25b5e11ebac07c072",
        "2020-P4 ": "27bc56da9e6a015f476611ebac07c172",
        "2020-P5 ": "27bc56da9e6a01f6ca6c11ebac07c272",
        "2020-P6 ": "27bc56da9e6a01f4617311ebac07c372",
        "2020-P7 ": "27bc56da9e6a01dab17a11ebac07c472",
        "2020-P8 ": "27bc56da9e6a01cddb8111ebac07c572",
        "2020-P9 ": "27bc56da9e6a0179bc8911ebac07c672",
        "2020-P10": "27bc56da9e6a01996d9111ebac07c772",
        "2020-P11": "27bc56da9e6a0125b89911ebac07c872",
        "2020-P12": "27bc56da9e6a011986a211ebac07c972",
        "2021-P1 ": "27bc56da9e6a015895fb17ebac07cb72",
        "2021-P2 ": "27bc56da9e6a0139040d18ebac07cc72",
        "2021-P3 ": "27bc56da9e6a01d39c1318ebac07cd72",
        "2021-P4 ": "27bc56da9e6a0178211a18ebac07ce72",
        "2021-P5 ": "27bc56da9e6a01af672018ebac07cf72",
        "2021-P6 ": "27bc56da9e6a01334e2718ebac07d072",
        "2021-P7 ": "27bc56da9e6a0190a22e18ebac07d172",
        "2021-P8 ": "27bc56da9e6a0178ad3618ebac07d272",
        "2021-P9 ": "27bc56da9e6a0112ad3e18ebac07d372",
        "2021-P10": "27bc56da9e6a0195e84618ebac07d472",
        "2021-P11": "27bc56da9e6a0184449a18ebac07d572",
        "2021-P12": "27bc56da9e6a015969a418ebac07d672",
        "2022-P1 ": "27bc56da9e6a0172d6691eebac07d872",
        "2022-P2 ": "27bc56da9e6a0162c67a1eebac07d972",
        "2022-P3 ": "27bc56da9e6a0127fa801eebac07da72",
        "2022-P4 ": "27bc56da9e6a0198d1871eebac07db72",
        "2022-P5 ": "27bc56da9e6a0128288e1eebac07dc72",
        "2022-P6 ": "27bc56da9e6a01f40f951eebac07dd72",
        "2022-P7 ": "27bc56da9e6a015efe9b1eebac07de72",
        "2022-P8 ": "27bc56da9e6a010e85a31eebac07df72",
        "2022-P9 ": "27bc56da9e6a018071fb1eebac07e072",
        "2022-P10": "27bc56da9e6a01bd23041febac07e172",
        "2022-P11": "27bc56da9e6a015daf0d1febac07e272",
        "2022-P12": "27bc56da9e6a0136b9161febac07e372",
        "2023-P1 ": "27bc56da9e6a01bc152125ebac07e572",
        "2023-P2 ": "27bc56da9e6a0181583125ebac07e672",
        "2023-P3 ": "27bc56da9e6a01f05a3725ebac07e772",
        "2023-P4 ": "27bc56da9e6a015e5f3d25ebac07e872",
        "2023-P5 ": "27bc56da9e6a01a2054425ebac07e972",
        "2023-P6 ": "27bc56da9e6a01fca14a25ebac07ea72",
        "2023-P7 ": "27bc56da9e6a01bf1f9e25ebac07eb72",
        "2023-P8 ": "27bc56da9e6a01fa2fa625ebac07ec72",
        "2023-P9 ": "27bc56da9e6a01c06aae25ebac07ed72",
        "2023-P10": "27bc56da9e6a013066b625ebac07ee72",
        "2023-P11": "27bc56da9e6a01523ebf25ebac07ef72",
        "2023-P12": "27bc56da9e6a01cac2c825ebac07f072",
        "2024-P1 ": "27bc56da9e6a01f074782bebac07f272",
        "2024-P2 ": "27bc56da9e6a01ef77892bebac07f372",
        "2024-P3 ": "27bc56da9e6a011f73902bebac07f472",
        "2024-P4 ": "27bc56da9e6a016197962bebac07f572",
        "2024-P5 ": "27bc56da9e6a010380f12bebac07f672",
        "2024-P6 ": "27bc56da9e6a01cffbf82bebac07f772",
        "2024-P7 ": "27bc56da9e6a018074002cebac07f872",
        "2024-P8 ": "27bc56da9e6a01bbc1072cebac07f972",
        "2024-P9 ": "27bc56da9e6a011da90f2cebac07fa72",
        "2024-P10": "27bc56da9e6a014e88172cebac07fb72",
        "2024-P11": "27bc56da9e6a01980e202cebac07fc72",
        "2024-P12": "27bc56da9e6a011403292cebac07fd72",
        "2025-P1 ": "27bc56da9e6a01ed617c32ebac07ff72",
        "2025-P2 ": "27bc56da9e6a01b6a48c32ebac070073",
        "2025-P3 ": "27bc56da9e6a010512d832ebac070173",
        "2025-P4 ": "27bc56da9e6a01dcd9de32ebac070273",
        "2025-P5 ": "27bc56da9e6a01a2b0e532ebac070373",
        "2025-P6 ": "27bc56da9e6a01496eec32ebac070473",
        "2025-P7 ": "27bc56da9e6a01d520f432ebac070573",
        "2025-P8 ": "27bc56da9e6a01cc63fb32ebac070673",
        "2025-P9 ": "27bc56da9e6a015a950333ebac070773",
        "2025-P10": "27bc56da9e6a012a3c0c33ebac070873",
        "2025-P11": "27bc56da9e6a0119451533ebac070973",
        "2025-P12": "27bc56da9e6a0165e91d33ebac070a73",
        "2026-P1 ": "27bc56da9e6a01a223b339ebac070c73",
        "2026-P2 ": "27bc56da9e6a016cd5c339ebac070d73",
        "2026-P3 ": "27bc56da9e6a01bfe1c939ebac070e73",
        "2026-P4 ": "27bc56da9e6a012e4bd039ebac070f73",
        "2026-P5 ": "27bc56da9e6a017196d639ebac071073",
        "2026-P6 ": "27bc56da9e6a018a6add39ebac071173",
        "2026-P7 ": "27bc56da9e6a01524fe439ebac071273",
        "2026-P8 ": "27bc56da9e6a017078eb39ebac071373",
        "2026-P9 ": "27bc56da9e6a01e239f339ebac071473",
        "2026-P10": "27bc56da9e6a017eeffa39ebac071573",
        "2026-P11": "27bc56da9e6a015171563aebac071673",
        "2026-P12": "27bc56da9e6a019923603aebac071773",
        "2027-P1 ": "27bc56da9e6a01460b7040ebac071973",
        "2027-P2 ": "27bc56da9e6a01a6118140ebac071a73",
        "2027-P3 ": "27bc56da9e6a011ee88640ebac071b73",
        "2027-P4 ": "27bc56da9e6a01fe028e40ebac071c73",
        "2027-P5 ": "27bc56da9e6a0156519440ebac071d73",
        "2027-P6 ": "27bc56da9e6a0199fb9b40ebac071e73",
        "2027-P7 ": "27bc56da9e6a01b613a340ebac071f73",
        "2027-P8 ": "27bc56da9e6a01a8a6aa40ebac072073",
        "2027-P9 ": "27bc56da9e6a014d60fd40ebac072173",
        "2027-P10": "27bc56da9e6a017a840641ebac072273",
        "2027-P11": "27bc56da9e6a017fe30e41ebac072373",
        "2027-P12": "27bc56da9e6a0101ef1741ebac072473",
        "2028-P1 ": "27bc56da9e6a0137622f47ebac072673",
        "2028-P2 ": "27bc56da9e6a01dcb43f47ebac072773",
        "2028-P3 ": "27bc56da9e6a01d9eb4547ebac072873",
        "2028-P4 ": "27bc56da9e6a0140d44c47ebac072973",
        "2028-P5 ": "27bc56da9e6a01ce4b5347ebac072a73",
        "2028-P6 ": "27bc56da9e6a01954c5a47ebac072b73",
        "2028-P7 ": "27bc56da9e6a010c00b747ebac072c73",
        "2028-P8 ": "27bc56da9e6a018916bf47ebac072d73",
        "2028-P9 ": "27bc56da9e6a011333c747ebac072e73",
        "2028-P10": "27bc56da9e6a013922cf47ebac072f73",
        "2028-P11": "27bc56da9e6a01169cd747ebac073073",
        "2028-P12": "27bc56da9e6a01db91e047ebac073173",
        "2029-P1 ": "27bc56da9e6a0173727c4eebac073373",
        "2029-P2 ": "27bc56da9e6a01c557924eebac073473",
        "2029-P3 ": "27bc56da9e6a017ecc984eebac073573",
        "2029-P4 ": "27bc56da9e6a01e7b19f4eebac073673",
        "2029-P5 ": "27bc56da9e6a01b2880c4febac073773",
        "2029-P6 ": "27bc56da9e6a015064144febac073873",
        "2029-P7 ": "27bc56da9e6a018a721c4febac073973",
        "2029-P8 ": "27bc56da9e6a01893e244febac073a73",
        "2029-P9 ": "27bc56da9e6a018b4e2c4febac073b73",
        "2029-P10": "27bc56da9e6a016e4c354febac073c73",
        "2029-P11": "27bc56da9e6a01e6f93d4febac073d73",
        "2029-P12": "27bc56da9e6a01a864474febac073e73",
        "2030-P1 ": "27bc56da9e6a01ea137c55ebac074073",
        "2030-P2 ": "27bc56da9e6a01d0ad8c55ebac074173",
        "2030-P3 ": "27bc56da9e6a014a47ff55ebac074273",
        "2030-P4 ": "27bc56da9e6a017d060656ebac074373",
        "2030-P5 ": "27bc56da9e6a01e7d30c56ebac074473",
        "2030-P6 ": "27bc56da9e6a01e1e61356ebac074573",
        "2030-P7 ": "27bc56da9e6a012ece1a56ebac074673",
        "2030-P8 ": "27bc56da9e6a016d4c2256ebac074773",
        "2030-P9 ": "27bc56da9e6a013e222a56ebac074873",
        "2030-P10": "27bc56da9e6a019ec53256ebac074973",
        "2030-P11": "27bc56da9e6a015c793b56ebac074a73",
        "2030-P12": "27bc56da9e6a01a3094556ebac074b73",
        "2015-P1 ": "7ef48c7d722701c30d506888670ed46b",
        "2015-P2 ": "7ef48c7d72270154f16a6888670ed56b",
        "2015-P3 ": "7ef48c7d7227012a13726888670ed66b",
        "2015-P4 ": "7ef48c7d7227012aaf766888670ed76b",
        "2015-P5 ": "7ef48c7d7227019e877b6888670ed86b",
        "2015-P6 ": "7ef48c7d722701212f806888670ed96b",
        "2015-P7 ": "7ef48c7d7227015305856888670eda6b",
        "2015-P8 ": "7ef48c7d7227018fef896888670edb6b",
        "2015-P9 ": "7ef48c7d7227011b668f6888670edc6b",
        "2015-P10": "7ef48c7d722701c3a7946888670edd6b",
        "2015-P11": "7ef48c7d7227016b41f76888670ede6b",
        "2015-P12": "7ef48c7d7227011f5cfe6888670edf6b",
        "2014-P1 ": "7ef48c7d7227010f3451708b670e516c",
        "2014-P2 ": "7ef48c7d722701b75e5b708b670e526c",
        "2014-P3 ": "7ef48c7d72270170686f708b670e536c",
        "2014-P4 ": "7ef48c7d722701363374708b670e546c",
        "2014-P5 ": "7ef48c7d722701c4bb78708b670e556c",
        "2014-P6 ": "7ef48c7d72270141be7d708b670e566c",
        "2014-P7 ": "7ef48c7d722701bb6682708b670e576c",
        "2014-P8 ": "7ef48c7d722701184887708b670e586c",
        "2014-P9 ": "7ef48c7d722701cd14ff708b670e596c",
        "2014-P10": "7ef48c7d7227016a4f06718b670e5a6c",
        "2014-P11": "7ef48c7d722701a9680c718b670e5b6c",
        "2014-P12": "7ef48c7d722701c90a13718b670e5c6c",
        "2013-P1 ": "7ef48c7d722701791e497c8e670ecd6c",
        "2013-P2 ": "7ef48c7d722701cc61537c8e670ece6c",
        "2013-P3 ": "7ef48c7d722701d03e587c8e670ecf6c",
        "2013-P4 ": "7ef48c7d72270192c25c7c8e670ed06c",
        "2013-P5 ": "7ef48c7d722701d63c617c8e670ed16c",
        "2013-P6 ": "7ef48c7d72270126dd657c8e670ed26c",
        "2013-P7 ": "7ef48c7d722701df31e37c8e670ed36c",
        "2013-P8 ": "7ef48c7d722701051eea7c8e670ed46c",
        "2013-P9 ": "7ef48c7d722701463cf07c8e670ed56c",
        "2013-P10": "7ef48c7d722701f3eaf57c8e670ed66c",
        "2013-P11": "7ef48c7d7227010c60fb7c8e670ed76c",
        "2013-P12": "7ef48c7d72270117ef017d8e670ed86c",
        "2012-P1 ": "7ef48c7d7227013811a61193670e5c6d",
        "2012-P2 ": "7ef48c7d722701b1d4b01193670e5d6d",
        "2012-P3 ": "7ef48c7d722701e24db51193670e5e6d",
        "2012-P4 ": "7ef48c7d722701df23ba1193670e5f6d",
        "2012-P5 ": "7ef48c7d7227019f65221293670e606d",
        "2012-P6 ": "7ef48c7d72270180b1281293670e616d",
        "2012-P7 ": "7ef48c7d7227016bc92d1293670e626d",
        "2012-P8 ": "7ef48c7d722701c573331293670e636d",
        "2012-P9 ": "7ef48c7d72270142e1381293670e646d",
        "2012-P10": "7ef48c7d722701c72a3e1293670e656d",
        "2012-P11": "7ef48c7d722701810e441293670e666d",
        "2012-P12": "7ef48c7d7227013ad8491293670e676d",
        "2011-P1 ": "7ef48c7d7227016186b98d95670ec56d",
        "2011-P2 ": "7ef48c7d7227018d16c48d95670ec66d",
        "2011-P3 ": "7ef48c7d722701ff45508e95670ec76d",
        "2011-P4 ": "7ef48c7d722701b7ad568e95670ec86d",
        "2011-P5 ": "7ef48c7d7227014bd55d8e95670ec96d",
        "2011-P6 ": "7ef48c7d722701379c638e95670eca6d",
        "2011-P7 ": "7ef48c7d72270182dd698e95670ecb6d",
        "2011-P8 ": "7ef48c7d722701f42d728e95670ecc6d",
        "2011-P9 ": "7ef48c7d722701bc117b8e95670ecd6d",
        "2011-P10": "7ef48c7d722701dd04818e95670ece6d",
        "2011-P11": "7ef48c7d722701b299898e95670ecf6d",
        "2011-P12": "7ef48c7d722701658e918e95670ed06d",
        "2010-P1 ": "7ef48c7d722701a9c9378f99670e226e",
        "2010-P2 ": "7ef48c7d7227014333438f99670e236e",
        "2010-P3 ": "7ef48c7d7227016bfe478f99670e246e",
        "2010-P4 ": "7ef48c7d722701255c4c8f99670e256e",
        "2010-P5 ": "7ef48c7d722701ddbf508f99670e266e",
        "2010-P6 ": "7ef48c7d722701c1ac558f99670e276e",
        "2010-P7 ": "7ef48c7d722701c0765a8f99670e286e",
        "2010-P8 ": "7ef48c7d722701546e5f8f99670e296e",
        "2010-P9 ": "7ef48c7d72270196d5648f99670e2a6e",
        "2010-P10": "7ef48c7d722701fd196a8f99670e2b6e",
        "2010-P11": "7ef48c7d722701969cd38f99670e2c6e",
        "2010-P12": "7ef48c7d722701a9e7da8f99670e2d6e",
        "2009-P1 ": "7ef48c7d72270142d05d519c670e8b6e",
        "2009-P2 ": "7ef48c7d7227014bc668519c670e8c6e",
        "2009-P3 ": "7ef48c7d7227013a3c6d519c670e8d6e",
        "2009-P4 ": "7ef48c7d722701249371519c670e8e6e",
        "2009-P5 ": "7ef48c7d722701c24876519c670e8f6e",
        "2009-P6 ": "7ef48c7d722701d5077b519c670e906e",
        "2009-P7 ": "7ef48c7d722701a7b67f519c670e916e",
        "2009-P8 ": "7ef48c7d722701cbfb84519c670e926e",
        "2009-P9 ": "7ef48c7d7227011d75f6519c670e936e",
        "2009-P10": "7ef48c7d722701a1effc519c670e946e",
        "2009-P11": "7ef48c7d7227013f1703529c670e956e",
        "2009-P12": "7ef48c7d722701d4f608529c670e966e",
        "2008-P1 ": "7ef48c7d7227018a372cec9e670ec86e",
        "2008-P2 ": "7ef48c7d722701868d3cec9e670ec96e",
        "2008-P3 ": "7ef48c7d722701617b43ec9e670eca6e",
        "2008-P4 ": "7ef48c7d722701582a4cec9e670ecb6e",
        "2008-P5 ": "7ef48c7d72270170d455ec9e670ecc6e",
        "2008-P6 ": "7ef48c7d7227012cba60ec9e670ecd6e",
        "2008-P7 ": "7ef48c7d722701fd42f3ec9e670ece6e",
        "2008-P8 ": "7ef48c7d722701a35dfaec9e670ecf6e",
        "2008-P9 ": "7ef48c7d722701e7bbffec9e670ed06e",
        "2008-P10": "7ef48c7d722701900605ed9e670ed16e",
        "2008-P11": "7ef48c7d722701e9fb0aed9e670ed26e",
        "2008-P12": "7ef48c7d722701ceb910ed9e670ed36e",
        "2007-P1 ": "7ef48c7d722701d3829ff6a1670e346f",
        "2007-P2 ": "7ef48c7d722701ca45abf6a1670e356f",
        "2007-P3 ": "7ef48c7d7227017e4bb0f6a1670e366f",
        "2007-P4 ": "7ef48c7d7227019cf3b4f6a1670e376f",
        "2007-P5 ": "7ef48c7d72270141262ff7a1670e386f",
        "2007-P6 ": "7ef48c7d722701dd6635f7a1670e396f",
        "2007-P7 ": "7ef48c7d722701eee53af7a1670e3a6f",
        "2007-P8 ": "7ef48c7d72270107fd3ff7a1670e3b6f",
        "2007-P9 ": "7ef48c7d722701cd2145f7a1670e3c6f",
        "2007-P10": "7ef48c7d7227014bd94af7a1670e3d6f",
        "2007-P11": "7ef48c7d7227013a6250f7a1670e3e6f",
        "2007-P12": "7ef48c7d722701682a56f7a1670e3f6f",
        "2006-P1 ": "7ef48c7d72270136d024baa4670e9d6f",
        "2006-P2 ": "7ef48c7d722701b2ae2fbaa4670e9e6f",
        "2006-P3 ": "7ef48c7d722701dae39fbaa4670e9f6f",
        "2006-P4 ": "7ef48c7d7227013666a5baa4670ea06f",
        "2006-P5 ": "7ef48c7d722701a226aabaa4670ea16f",
        "2006-P6 ": "7ef48c7d7227017e81afbaa4670ea26f",
        "2006-P7 ": "7ef48c7d7227011a6fb4baa4670ea36f",
        "2006-P8 ": "7ef48c7d722701a27db9baa4670ea46f",
        "2006-P9 ": "7ef48c7d7227012e23bfbaa4670ea56f",
        "2006-P10": "7ef48c7d722701487cc4baa4670ea66f",
        "2006-P11": "7ef48c7d72270161f1c9baa4670ea76f",
        "2006-P12": "7ef48c7d722701da1ed0baa4670ea86f",
        "2005-P1 ": "7ef48c7d7227013d34d9e2a7670ed66f",
        "2005-P2 ": "7ef48c7d722701c232e6e2a7670ed76f",
        "2005-P3 ": "7ef48c7d722701cf72ebe2a7670ed86f",
        "2005-P4 ": "7ef48c7d72270180e9efe2a7670ed96f",
        "2005-P5 ": "7ef48c7d722701bc70f4e2a7670eda6f",
        "2005-P6 ": "7ef48c7d722701cba4f9e2a7670edb6f",
        "2005-P7 ": "7ef48c7d722701de88fee2a7670edc6f",
        "2005-P8 ": "7ef48c7d722701a78a03e3a7670edd6f",
        "2005-P9 ": "7ef48c7d722701d06109e3a7670ede6f",
        "2005-P10": "7ef48c7d7227014fbf0ee3a7670edf6f",
        "2005-P11": "7ef48c7d722701dae572e3a7670ee06f",
        "2005-P12": "7ef48c7d7227014d5c7ae3a7670ee16f",
        "2004-P1 ": "7ef48c7d722701a284edbb697c0ea7b6",
        "2004-P2 ": "7ef48c7d722701ede0f9bb697c0ea8b6",
        "2004-P3 ": "7ef48c7d7227019876febb697c0ea9b6",
        "2004-P4 ": "7ef48c7d7227016ccb02bc697c0eaab6",
        "2004-P5 ": "7ef48c7d7227015d3807bc697c0eabb6",
        "2004-P6 ": "7ef48c7d722701e32e0cbc697c0eacb6",
        "2004-P7 ": "7ef48c7d7227019dfc10bc697c0eadb6",
        "2004-P8 ": "7ef48c7d7227014ce615bc697c0eaeb6",
        "2004-P9 ": "7ef48c7d722701108794bc697c0eafb6",
        "2004-P10": "7ef48c7d72270191d39abc697c0eb0b6",
        "2004-P11": "7ef48c7d7227011573a0bc697c0eb1b6",
        "2004-P12": "7ef48c7d722701edb5a6bc697c0eb2b6",
        "2031-P1 ": "ec006995113001104a0a6d1c3a06bd17",
        "2031-P2 ": "ec0069951130012b454c6d1c3a06be17",
        "2031-P3 ": "ec00699511300109765a6d1c3a06bf17",
        "2031-P4 ": "ec0069951130012f7f686d1c3a06c017",
        "2031-P5 ": "ec00699511300152c1766d1c3a06c117",
        "2031-P6 ": "ec0069951130010115856d1c3a06c217",
        "2031-P7 ": "ec006995113001f99c936d1c3a06c317",
        "2031-P8 ": "ec0069951130018900a26d1c3a06c417",
        "2031-P9 ": "ec0069951130019947b06d1c3a06c517",
        "2031-P10": "ec006995113001d941bf6d1c3a06c617",
        "2031-P11": "ec006995113001de2c226e1c3a06c717",
        "2031-P12": "ec00699511300147d9326e1c3a06c817",
        "2032-P1 ": "e717b61cab5d016ccf0f72dbfb007721",
        "2032-P2 ": "e717b61cab5d0161504872dbfb007821",
        "2032-P3 ": "e717b61cab5d01c50b5572dbfb007921",
        "2032-P4 ": "e717b61cab5d01bd7f6172dbfb007a21",
        "2032-P5 ": "e717b61cab5d0196196e72dbfb007b21",
        "2032-P6 ": "e717b61cab5d019cbc7a72dbfb007c21",
        "2032-P7 ": "e717b61cab5d015b7f8772dbfb007d21",
        "2032-P8 ": "e717b61cab5d016fc09772dbfb007e21",
        "2032-P9 ": "e717b61cab5d016caea672dbfb007f21",
        "2032-P10": "e717b61cab5d016574b472dbfb008021",
        "2032-P11": "e717b61cab5d01dbd64673dbfb008121",
        "2032-P12": "e717b61cab5d010ea75573dbfb008221",
        "2034-P1 ": "e717b61cab5d01f3c2c0b1e7fb008621",
        "2034-P2 ": "e717b61cab5d01a661dcb1e7fb008721",
        "2034-P3 ": "e717b61cab5d01ae1ff5b1e7fb008821",
        "2034-P4 ": "e717b61cab5d01448a04b2e7fb008921",
        "2034-P5 ": "e717b61cab5d01c9a51bb2e7fb008a21",
        "2034-P6 ": "e717b61cab5d0151cf28b2e7fb008b21",
        "2034-P7 ": "e717b61cab5d01c95735b2e7fb008c21",
        "2034-P8 ": "e717b61cab5d01190348b2e7fb008d21",
        "2033-P1 ": "541328409538019b12e1d9e3fb003d21",
        "2033-P2 ": "5413284095380190be15dae3fb003e21",
        "2033-P3 ": "54132840953801db7f22dae3fb003f21",
        "2033-P4 ": "54132840953801881b2fdae3fb004021",
        "2033-P5 ": "54132840953801c1e93bdae3fb004121",
        "2033-P6 ": "54132840953801282449dae3fb004221",
        "2033-P7 ": "5413284095380174435cdae3fb004321",
        "2033-P8 ": "5413284095380193a46adae3fb004421",
        "2033-P9 ": "54132840953801ac3078dae3fb004521",
        "2033-P10": "54132840953801dfee85dae3fb004621",
        "2033-P11": "5413284095380173eff1dae3fb004721",
        "2033-P12": "54132840953801ec2601dbe3fb004821",
        "2035-P1 ": "541328409538010154016a43ef01c1e0",
        "2035-P2 ": "541328409538017e6a0f6a43ef01c2e0",
        "2035-P3 ": "541328409538013a02186a43ef01c3e0",
        "2035-P4 ": "54132840953801000d206a43ef01c4e0",
        "2035-P5 ": "541328409538010a95286a43ef01c5e0",
        "2035-P6 ": "54132840953801473b316a43ef01c6e0",
        "2035-P7 ": "54132840953801beb8396a43ef01c7e0",
        "2035-P8 ": "541328409538014ac7426a43ef01c8e0",
        "2034-P9 ": "e717b61cab5d01bea0d0b2e7fb008e21",
        "2034-P10": "e717b61cab5d010871deb2e7fb008f21",
        "2034-P11": "e717b61cab5d0148a3edb2e7fb009021",
        "2034-P12": "e717b61cab5d012ab7fbb2e7fb009121",
        "2037-P1 ": "e717b61cab5d01d839016950ef0199d5",
        "2037-P2 ": "e717b61cab5d010a21136950ef019ad5",
        "2037-P3 ": "e717b61cab5d01b0771a6950ef019bd5",
        "2037-P4 ": "e717b61cab5d011f61216950ef019cd5",
        "2037-P5 ": "e717b61cab5d01e8df286950ef019dd5",
        "2037-P6 ": "e717b61cab5d01dc3d306950ef019ed5",
        "2035-P9 ": "541328409538011a00d86a43ef01c9e0",
        "2035-P10": "54132840953801f47fe26a43ef01cae0",
        "2035-P11": "541328409538016068ec6a43ef01cbe0",
        "2035-P12": "54132840953801b3aaf66a43ef01cce0",
        "2036-P1 ": "6768bef0a295018c05165e4fef01f1c7",
        "2036-P2 ": "6768bef0a29501e335425e4fef01f2c7",
        "2036-P3 ": "6768bef0a2950199a64b5e4fef01f3c7",
        "2036-P4 ": "6768bef0a29501e974545e4fef01f4c7",
        "2036-P5 ": "6768bef0a2950177c35d5e4fef01f5c7",
        "2036-P6 ": "6768bef0a2950167c6665e4fef01f6c7",
        "2036-P7 ": "6768bef0a295012b66705e4fef01f7c7",
        "2036-P8 ": "6768bef0a29501a63c7a5e4fef01f8c7",
        "2036-P9 ": "6768bef0a2950106ca835e4fef01f9c7",
        "2036-P10": "6768bef0a29501e4e88d5e4fef01fac7",
        "2036-P11": "6768bef0a295010951e55e4fef01fbc7",
        "2036-P12": "6768bef0a29501ec9af05e4fef01fcc7",
        "2039-P1 ": "6768bef0a2950100401e0457ef011fc8",
        "2039-P2 ": "6768bef0a29501a55e3f0457ef0120c8",
        "2039-P3 ": "6768bef0a2950194974b0457ef0121c8",
        "2039-P4 ": "6768bef0a2950106e7590457ef0122c8",
        "2039-P5 ": "6768bef0a29501da69630457ef0123c8",
        "2039-P6 ": "6768bef0a29501dce56c0457ef0124c8",
        "2039-P7 ": "6768bef0a29501a4b8760457ef0125c8",
        "2039-P8 ": "6768bef0a29501b540820457ef0126c8",
        "2037-P7 ": "e717b61cab5d01898a9a6950ef019fd5",
        "2037-P8 ": "e717b61cab5d010c49a56950ef01a0d5",
        "2037-P9 ": "e717b61cab5d01cc2db66950ef01a1d5",
        "2037-P10": "e717b61cab5d019526c26950ef01a2d5",
        "2037-P11": "e717b61cab5d01ea02cb6950ef01a3d5",
        "2037-P12": "e717b61cab5d010ea7d36950ef01a4d5",
        "2040-P1 ": "e717b61cab5d0155b5610759ef01b1d5",
        "2040-P2 ": "e717b61cab5d014afe740759ef01b2d5",
        "2040-P3 ": "e717b61cab5d01485e7c0759ef01b3d5",
        "2040-P4 ": "e717b61cab5d011953830759ef01b4d5",
        "2038-P1 ": "377d9401bc73016f0c253753ef0108bf",
        "2038-P2 ": "377d9401bc7301b2a8513753ef0109bf",
        "2038-P3 ": "377d9401bc73012abb593753ef010abf",
        "2038-P4 ": "377d9401bc7301a12c623753ef010bbf",
        "2038-P5 ": "377d9401bc73018f32773753ef010cbf",
        "2038-P6 ": "377d9401bc73013013853753ef010dbf",
        "2038-P7 ": "377d9401bc73015b088e3753ef010ebf",
        "2038-P8 ": "377d9401bc73019972963753ef010fbf",
        "2038-P9 ": "377d9401bc7301a9839f3753ef0110bf",
        "2038-P10": "377d9401bc7301a573a83753ef0111bf",
        "2038-P11": "377d9401bc7301abd6043853ef0112bf",
        "2038-P12": "377d9401bc73018cc20f3853ef0113bf",
        "2039-P9 ": "6768bef0a295015329f60457ef0127c8",
        "2039-P10": "6768bef0a29501aab6000557ef0128c8",
        "2039-P11": "6768bef0a2950147490b0557ef0129c8",
        "2039-P12": "6768bef0a29501d012160557ef012ac8",
        "2040-P5 ": "e717b61cab5d01c363ea0759ef01b5d5",
        "2040-P6 ": "e717b61cab5d012e37f30759ef01b6d5",
        "2040-P7 ": "e717b61cab5d0131e0fa0759ef01b7d5",
        "2040-P8 ": "e717b61cab5d019302030859ef01b8d5",
        "2040-P9 ": "e717b61cab5d0146e20a0859ef01b9d5",
        "2040-P10": "e717b61cab5d01130b130859ef01bad5",
        "2040-P11": "e717b61cab5d0104741b0859ef01bbd5",
        "2040-P12": "e717b61cab5d01e3e0240859ef01bcd5",
        "2003-P1 ": "ec6aaccdf643017eb96919cbcc01cc71",
        "2003-P2 ": "ec6aaccdf643016c368919cbcc01cd71",
        "2003-P3 ": "ec6aaccdf643019d7b8f19cbcc01ce71",
        "2003-P4 ": "ec6aaccdf643011e479519cbcc01cf71",
        "2003-P5 ": "ec6aaccdf6430113e29a19cbcc01d071",
        "2003-P6 ": "ec6aaccdf64301294fcc19cbcc01d171",
        "2003-P7 ": "ec6aaccdf643019a26d319cbcc01d271",
        "2003-P8 ": "ec6aaccdf6430197efd819cbcc01d371",
        "2003-P9 ": "ec6aaccdf64301feefde19cbcc01d471",
        "2003-P10": "ec6aaccdf64301add5e419cbcc01d571",
        "2003-P11": "ec6aaccdf643011a2d4a1acbcc01d671",
        "2003-P12": "ec6aaccdf64301b4ff511acbcc01d771",
        "2002-P1 ": "ec6aaccdf64301525ad909cfcc01d971",
        "2002-P2 ": "ec6aaccdf643013a97eb09cfcc01da71",
        "2002-P3 ": "ec6aaccdf64301c5ddf009cfcc01db71",
        "2002-P4 ": "ec6aaccdf643012034f609cfcc01dc71",
        "2002-P5 ": "ec6aaccdf64301c267fb09cfcc01dd71",
        "2002-P6 ": "ec6aaccdf643010d99000acfcc01de71",
        "2002-P7 ": "ec6aaccdf643018c4b060acfcc01df71",
        "2002-P8 ": "ec6aaccdf6430178e00b0acfcc01e071",
        "2002-P9 ": "ec6aaccdf643010249610acfcc01e171",
        "2002-P10": "ec6aaccdf64301c875670acfcc01e271",
        "2002-P11": "ec6aaccdf64301bb216d0acfcc01e371",
        "2002-P12": "ec6aaccdf643010258730acfcc01e471",
        "2000-P1 ": "ec6aaccdf643013f9cd8b1d6cc01e671",
        "2000-P2 ": "ec6aaccdf64301da24ebb1d6cc01e771",
        "2000-P3 ": "ec6aaccdf643013645f0b1d6cc01e871",
        "2000-P4 ": "ec6aaccdf64301dfbaf4b1d6cc01e971",
        "2000-P5 ": "ec6aaccdf643017247f9b1d6cc01ea71",
        "2000-P6 ": "ec6aaccdf6430167e9fdb1d6cc01eb71",
        "2001-P1 ": "7f360f7ecd5a013c7f459cd3cc013c7a",
        "2001-P2 ": "7f360f7ecd5a011bdf679cd3cc013d7a",
        "2001-P3 ": "7f360f7ecd5a01ff736e9cd3cc013e7a",
        "2001-P4 ": "7f360f7ecd5a0172e2739cd3cc013f7a",
        "2001-P5 ": "7f360f7ecd5a01210f7a9cd3cc01407a",
        "2001-P6 ": "7f360f7ecd5a01cc7caf9cd3cc01417a",
        "2001-P7 ": "7f360f7ecd5a01a486b69cd3cc01427a",
        "2001-P8 ": "7f360f7ecd5a019d5ebc9cd3cc01437a",
        "2001-P9 ": "7f360f7ecd5a01831bc29cd3cc01447a",
        "2001-P10": "7f360f7ecd5a017135c89cd3cc01457a",
        "2001-P11": "7f360f7ecd5a018628219dd3cc01467a",
        "2001-P12": "7f360f7ecd5a015f8b2a9dd3cc01477a",
        "1999-P1 ": "7f360f7ecd5a0127bfe6ffd9cc01547a",
        "1999-P2 ": "7f360f7ecd5a014dcef8ffd9cc01557a",
        "1999-P3 ": "7f360f7ecd5a0163a0fdffd9cc01567a",
        "1999-P4 ": "7f360f7ecd5a0102fb0100dacc01577a",
        "1999-P5 ": "7f360f7ecd5a01e2e10600dacc01587a",
        "1999-P6 ": "7f360f7ecd5a01207d0b00dacc01597a",
        "1999-P7 ": "7f360f7ecd5a018e451000dacc015a7a",
        "1999-P8 ": "7f360f7ecd5a0170aa1500dacc015b7a",
        "2000-P7 ": "ec6aaccdf64301afc370b2d6cc01ec71",
        "2000-P8 ": "ec6aaccdf64301d12678b2d6cc01ed71",
        "2000-P9 ": "ec6aaccdf64301dbf27db2d6cc01ee71",
        "2000-P10": "ec6aaccdf64301665383b2d6cc01ef71",
        "2000-P11": "ec6aaccdf64301842389b2d6cc01f071",
        "2000-P12": "ec6aaccdf6430144fb8eb2d6cc01f171",
        "1999-P9 ": "7f360f7ecd5a01622e3001dacc015c7a",
        "1999-P10": "7f360f7ecd5a01070c3b01dacc015d7a",
        "1999-P11": "7f360f7ecd5a01e6804101dacc015e7a",
        "1999-P12": "7f360f7ecd5a01ca744801dacc015f7a",
        "1996-P1 ": "7f360f7ecd5a01c7eae99ee4cc01617a",
        "1996-P2 ": "7f360f7ecd5a01a248fd9ee4cc01627a",
        "1996-P3 ": "7f360f7ecd5a01c75d029fe4cc01637a",
        "1996-P4 ": "7f360f7ecd5a014fc4069fe4cc01647a",
        "1996-P5 ": "7f360f7ecd5a0171570b9fe4cc01657a",
        "1996-P6 ": "7f360f7ecd5a01f8d30f9fe4cc01667a",
        "1998-P1 ": "fd739034dda3018584923edccc019b78",
        "1998-P2 ": "fd739034dda30106ffad3edccc019c78",
        "1998-P3 ": "fd739034dda301084bb43edccc019d78",
        "1998-P4 ": "fd739034dda3017103ba3edccc019e78",
        "1998-P5 ": "fd739034dda301d912c03edccc019f78",
        "1998-P6 ": "fd739034dda30128bcc53edccc01a078",
        "1998-P7 ": "fd739034dda301d1eccb3edccc01a178",
        "1998-P8 ": "fd739034dda30115acd13edccc01a278",
        "1998-P9 ": "fd739034dda301eb37ee3edccc01a378",
        "1998-P10": "fd739034dda3011cb7f43edccc01a478",
        "1998-P11": "fd739034dda3014104843fdccc01a578",
        "1998-P12": "fd739034dda30185908b3fdccc01a678",
        "1997-P1 ": "d4692729218f0185770b1fe0cc01bd79",
        "1997-P2 ": "d4692729218f01ae50261fe0cc01be79",
        "1997-P3 ": "d4692729218f0115932b1fe0cc01bf79",
        "1997-P4 ": "d4692729218f016500301fe0cc01c079",
        "1997-P5 ": "d4692729218f01188d341fe0cc01c179",
        "1997-P6 ": "d4692729218f01207a391fe0cc01c279",
        "1997-P7 ": "d4692729218f01b723531fe0cc01c379",
        "1997-P8 ": "d4692729218f0161fd581fe0cc01c479",
        "1997-P9 ": "d4692729218f0107365e1fe0cc01c579",
        "1997-P10": "d4692729218f01d8c4631fe0cc01c679",
        "1997-P11": "d4692729218f01e634b81fe0cc01c779",
        "1997-P12": "d4692729218f015dabbf1fe0cc01c879",
        "1996-P7 ": "7f360f7ecd5a01d6a2829fe4cc01677a",
        "1996-P8 ": "7f360f7ecd5a015b278c9fe4cc01687a",
        "1996-P9 ": "7f360f7ecd5a01ed39929fe4cc01697a",
        "1996-P10": "7f360f7ecd5a01ece4979fe4cc016a7a",
        "1996-P11": "7f360f7ecd5a010e019e9fe4cc016b7a",
        "1996-P12": "7f360f7ecd5a014426a49fe4cc016c7a",
        "1995-P1 ": "7f360f7ecd5a017edb0a1c6fd0018f7a",
        "1995-P2 ": "7f360f7ecd5a01eae31f1c6fd001907a",
        "1995-P3 ": "7f360f7ecd5a010eec251c6fd001917a",
        "1995-P4 ": "7f360f7ecd5a0151a72b1c6fd001927a",
        "1995-P5 ": "7f360f7ecd5a01e6c4bb1c6fd001937a",
        "1995-P6 ": "7f360f7ecd5a01d0d4c41c6fd001947a",
        "1995-P7 ": "7f360f7ecd5a01b643cb1c6fd001957a",
        "1995-P8 ": "7f360f7ecd5a010487d11c6fd001967a",
        "1995-P9 ": "7f360f7ecd5a01d181d71c6fd001977a",
        "1995-P10": "7f360f7ecd5a016690dd1c6fd001987a",
        "1995-P11": "7f360f7ecd5a011d03e41c6fd001997a",
        "1995-P12": "7f360f7ecd5a017271ea1c6fd0019a7a",
        "1994-P1 ": "7f360f7ecd5a0194c39da071d0019c7a",
        "1994-P2 ": "7f360f7ecd5a01879fafa071d0019d7a",
        "1994-P3 ": "7f360f7ecd5a01cf3d68a171d0019e7a",
        "1994-P4 ": "7f360f7ecd5a01888a70a171d0019f7a",
        "1994-P5 ": "7f360f7ecd5a01c18975a171d001a07a",
        "1994-P6 ": "7f360f7ecd5a01692e7aa171d001a17a",
        "1994-P7 ": "7f360f7ecd5a01ae427fa171d001a27a",
        "1994-P8 ": "7f360f7ecd5a01153584a171d001a37a",
        "1994-P9 ": "7f360f7ecd5a01933289a171d001a47a",
        "1994-P10": "7f360f7ecd5a01d69e8ea171d001a57a",
        "1994-P11": "7f360f7ecd5a01a00e94a171d001a67a",
        "1994-P12": "7f360f7ecd5a01b6b399a171d001a77a",
        "2041-P1 ": "11c51efb63551000e04779df50ee0000",
        "2041-P2 ": "11c51efb63551000e04779df50ee0001",
        "2041-P3 ": "11c51efb63551000e04779df50ee0002",
        "2041-P4 ": "11c51efb63551000e0477a78e5f90000",
        "2041-P5 ": "11c51efb63551000e0477a78e5f90001",
        "2041-P6 ": "11c51efb63551000e0477a78e5f90002",
        "2041-P7 ": "11c51efb63551000e0477a78e5f90003",
        "2041-P8 ": "11c51efb63551000e0477a78e5f90004",
        "2041-P9 ": "11c51efb63551000e0477b1293910000",
        "2041-P10": "11c51efb63551000e0477b1293910001",
        "2041-P11": "11c51efb63551000e0477b1293910002",
        "2041-P12": "11c51efb63551000e0477bac17ad0000",
        "2042-P1 ": "24156fb7f9d01000e04d5863a5da0000",
        "2042-P2 ": "24156fb7f9d01000e04d5863a5da0001",
        "2042-P3 ": "24156fb7f9d01000e04d5863a5da0002",
        "2042-P4 ": "24156fb7f9d01000e04d58fd5e5e0000",
        "2042-P5 ": "24156fb7f9d01000e04d58fd5e5e0001",
        "2042-P6 ": "24156fb7f9d01000e04d58fd5e5e0002",
        "2042-P7 ": "24156fb7f9d01000e04d58fd5e5e0003",
        "2042-P8 ": "24156fb7f9d01000e04d58fd5e5e0004",
        "2042-P9 ": "24156fb7f9d01000e04d599740640000",
        "2042-P10": "24156fb7f9d01000e04d599740640001",
        "2042-P11": "24156fb7f9d01000e04d599740640002",
        "2042-P12": "24156fb7f9d01000e04d5a3114850000",
        "2043-P1 ": "ba1d864aefb61000e056018f92ea0000",
        "2043-P2 ": "ba1d864aefb61000e056018f92ea0001",
        "2043-P3 ": "ba1d864aefb61000e056018f92ea0002",
        "2043-P4 ": "ba1d864aefb61000e056018f92ea0003",
        "2043-P5 ": "ba1d864aefb61000e056022959e00000",
        "2043-P6 ": "ba1d864aefb61000e056022959e00001",
        "2043-P7 ": "ba1d864aefb61000e056022959e00002",
        "2043-P8 ": "ba1d864aefb61000e056022959e00003",
        "2043-P9 ": "ba1d864aefb61000e056022959e00004",
        "2043-P10": "ba1d864aefb61000e05602c3202a0000",
        "2043-P11": "ba1d864aefb61000e05602c3202a0001",
        "2043-P12": "ba1d864aefb61000e05602c3202a0002",
        "2044-P1 ": "91629137d4eb1001c015a2dd31f60000",
        "2044-P2 ": "91629137d4eb1001c015a2dd31f60001",
        "2044-P3 ": "91629137d4eb1001c015a2dd31f60002",
        "2044-P4 ": "91629137d4eb1001c015a376edec0000",
        "2044-P5 ": "91629137d4eb1001c015a376edec0001",
        "2044-P6 ": "91629137d4eb1001c015a376edec0002",
        "2044-P7 ": "91629137d4eb1001c015a376edec0003",
        "2044-P8 ": "91629137d4eb1001c015a4107ce70000",
        "2044-P9 ": "91629137d4eb1001c015a4107ce70001",
        "2044-P10": "91629137d4eb1001c015a4107ce70002",
        "2044-P11": "91629137d4eb1001c015a4aa3c5d0000",
        "2044-P12": "91629137d4eb1001c015a4aa3c5d0001",
        "2045-P1 ": "91629137d4eb1001c019b9f382b40000",
        "2045-P2 ": "91629137d4eb1001c019b9f382b40001",
        "2045-P3 ": "91629137d4eb1001c019b9f382b40002",
        "2045-P4 ": "91629137d4eb1001c019ba8d28ae0000",
        "2045-P5 ": "91629137d4eb1001c019ba8d28ae0001",
        "2045-P6 ": "91629137d4eb1001c019ba8d28ae0002",
        "2045-P7 ": "91629137d4eb1001c019ba8d28ae0003",
        "2045-P8 ": "91629137d4eb1001c019bb26d90c0000",
        "2045-P9 ": "91629137d4eb1001c019bb26d90c0001",
        "2045-P10": "91629137d4eb1001c019bbc093c10000",
        "2045-P11": "91629137d4eb1001c019bbc093c10001",
        "2045-P12": "91629137d4eb1001c019bbc093c10002",
        "2046-P1 ": "5350f41bb8051001c01fdb7c107c0001",
        "2046-P2 ": "5350f41bb8051001c01fdc1599b30000",
        "2046-P3 ": "5350f41bb8051001c01fdc1599b30001",
        "2046-P4 ": "5350f41bb8051001c01fdc1599b30002",
        "2046-P5 ": "5350f41bb8051001c01fdc1599b30003",
        "2046-P6 ": "5350f41bb8051001c01fdcaf48420000",
        "2046-P7 ": "5350f41bb8051001c01fdcaf48420001",
        "2046-P8 ": "5350f41bb8051001c01fdcaf48420002",
        "2046-P9 ": "5350f41bb8051001c01fdcaf48420003",
        "2046-P10": "5350f41bb8051001c01fdd490cf50000",
        "2046-P11": "5350f41bb8051001c01fdd490cf50001",
        "2046-P12": "5350f41bb8051001c01fdd490cf50002",
        "2047-P1 ": "449c5c3bd8f71001c0222202ef9c0000",
        "2047-P2 ": "449c5c3bd8f71001c0222202ef9c0001",
        "2047-P3 ": "449c5c3bd8f71001c022229cb5820000",
        "2047-P4 ": "449c5c3bd8f71001c022229cb5820001",
        "2047-P5 ": "449c5c3bd8f71001c022229cb5820002",
        "2047-P6 ": "449c5c3bd8f71001c022229cb5820003",
        "2047-P7 ": "449c5c3bd8f71001c02223363e790000",
        "2047-P8 ": "449c5c3bd8f71001c02223363e790001",
        "2047-P9 ": "449c5c3bd8f71001c02223363e790002",
        "2047-P10": "449c5c3bd8f71001c02223363e790003",
        "2047-P11": "449c5c3bd8f71001c02223cfcb710000",
        "2047-P12": "449c5c3bd8f71001c02223cfcb710001",
        "2048-P1 ": "449c5c3bd8f71001c024fd82efea0000",
        "2048-P2 ": "449c5c3bd8f71001c024fd82efea0001",
        "2048-P3 ": "449c5c3bd8f71001c024fd82efea0002",
        "2048-P4 ": "449c5c3bd8f71001c024fd82efea0003",
        "2048-P5 ": "449c5c3bd8f71001c024fe1c7bf30000",
        "2048-P6 ": "449c5c3bd8f71001c024fe1c7bf30001",
        "2048-P7 ": "449c5c3bd8f71001c024fe1c7bf30002",
        "2048-P8 ": "449c5c3bd8f71001c024fe1c7bf30003",
        "2048-P9 ": "449c5c3bd8f71001c024feb620d10000",
        "2048-P10": "449c5c3bd8f71001c024ff4fd03c0000",
        "2048-P11": "449c5c3bd8f71001c024ff4fd03c0001",
        "2048-P12": "449c5c3bd8f71001c024ff4fd03c0002",
        "2049-P1 ": "ba6ad33f40121001c02788a5b6d90000",
        "2049-P2 ": "ba6ad33f40121001c02788a5b6d90001",
        "2049-P3 ": "ba6ad33f40121001c02788a5b6d90002",
        "2049-P4 ": "ba6ad33f40121001c02788a5b6d90003",
        "2049-P5 ": "ba6ad33f40121001c027893f46b80000",
        "2049-P6 ": "ba6ad33f40121001c027893f46b80001",
        "2049-P7 ": "ba6ad33f40121001c027893f46b80002",
        "2049-P8 ": "ba6ad33f40121001c027893f46b80003",
        "2049-P9 ": "ba6ad33f40121001c027893f46b80004",
        "2049-P10": "ba6ad33f40121001c02789d8d4b80000",
        "2049-P11": "ba6ad33f40121001c02789d8d4b80001",
        "2049-P12": "ba6ad33f40121001c02789d8d4b80002",
        "2050-P1 ": "f3a4c5aa2f081001c02a8e1a45b60000",
        "2050-P2 ": "f3a4c5aa2f081001c02a8e1a45b60001",
        "2050-P3 ": "f3a4c5aa2f081001c02a8eb400460000",
        "2050-P4 ": "f3a4c5aa2f081001c02a8eb400460001",
        "2050-P5 ": "f3a4c5aa2f081001c02a8eb400460002",
        "2050-P6 ": "f3a4c5aa2f081001c02a8eb400460003",
        "2050-P7 ": "f3a4c5aa2f081001c02a8eb400460004",
        "2050-P8 ": "f3a4c5aa2f081001c02a8eb400460005",
        "2050-P9 ": "f3a4c5aa2f081001c02a8f4da3260000",
        "2050-P10": "f3a4c5aa2f081001c02a8f4da3260001",
        "2050-P11": "f3a4c5aa2f081001c02a8f4da3260002",
        "2050-P12": "f3a4c5aa2f081001c02a8f4da3260003",
    }
    WID_periods = "&Period%21WID="
    for i in range(period):
        period_int = i + 1
        if period_int < 10:
            period_str = str(period_int) + " "
        else:
            period_str = str(period_int)

        key = f"{year}-P{period_str}"
        print(key)
        WID_period = table[key]
        WID_periods += WID_period + "!"

    # removing the last "!"
    WID_periods = WID_periods[:-1]
    print(WID_periods)
    return WID_periods
