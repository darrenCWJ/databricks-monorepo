import json
import os
import urllib
import uuid
from datetime import datetime, timedelta

import jwt
import requests
from databricks.sdk.runtime import *


def get_key(key):
    key = json.dumps(key)
    key = jwt.algorithms.ECAlgorithm.from_jwk(key)
    return key


class SharePointOnline:
    def __init__(self, verbose=False, **kwargs):
        self.verbose = verbose
        self.parameter = kwargs
        self.list_of_items = []
        self.list_of_child = []
        self.filtered_parent = []
        self.filtered_child = []
        self.first_load = dbutils.widgets.get("FIRST_LOAD")
        self.reload = dbutils.widgets.get("RELOAD")
        self.env = dbutils.widgets.get("ENV")
        self.project = dbutils.widgets.get("PROJECT")
        self.time_interval = self.gen_time_interval()

        if not kwargs.get("api_details").get("api_sub_site_id"):
            self.url_base = f"https://public.api.gov.sg/gig-collab-dart/v1.0/sites/{kwargs.get('api_details').get('api_site_id')}/"
            self.url_ms_base = f"https://graph.microsoft.com/v1.0/sites/{kwargs.get('api_details').get('api_site_id')}/"
        else:
            self.url_base = f"https://public.api.gov.sg/gig-collab-dart/v1.0/sites/{kwargs.get('api_details').get('api_site_id')}/sites/{kwargs.get('api_sub_site_id')}/"
            self.url_ms_base = f"https://graph.microsoft.com/v1.0/sites/{kwargs.get('api_details').get('api_site_id')}/sites/{kwargs.get('api_details').get('api_sub_site_id')}/"

        if not kwargs.get("api_details").get("api_secret_token"):
            self.token = dbutils.secrets.get(
                kwargs.get("api_details").get("api_secret"), "databricks"
            )
        else:
            self.token = kwargs.get("api_details").get("api_secret_token")

    def print_verbose(self, message):
        if self.verbose:
            print(message)

    @staticmethod
    def convert_to_bool(input_string):
        if input_string.lower() == "true":
            return True
        elif input_string.lower() == "false":
            return False
        else:
            raise ValueError("Input string must be 'True' or 'False'")

    def gen_time_interval(self):
        valid_keys = ["days", "hours", "minutes", "seconds", "microseconds", "milliseconds"]
        filtered_kwargs = {
            key: value
            for key, value in self.parameter.get("time_interval").items()
            if key in valid_keys
        }
        current_time = datetime.utcnow()

        # if self.convert_to_bool(self.reload):
        if self.convert_to_bool(self.first_load) or self.convert_to_bool(self.reload):
            reload_year = 2023
            timestamp = datetime(reload_year, 1, 1).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.print_verbose(f"Reloading Data, initial full data collection since {reload_year}")
        else:
            time_before = current_time - timedelta(**filtered_kwargs)
            timestamp = time_before.strftime("%Y-%m-%dT%H:%M:%SZ")

        return timestamp

    @staticmethod
    def append_datetime_to_filename(file_name, lastModifiedDateTime):
        file_name, file_extension = os.path.splitext(file_name)
        # date_time = lastModifiedDateTime
        lastModifiedDateTime = lastModifiedDateTime.replace(":", "-")
        new_file_name = f"{file_name}_{lastModifiedDateTime}{file_extension}"
        return new_file_name

    def sharepoint_requests(self, url):
        url
        modified_url = urllib.parse.urljoin(self.url_base, url)
        jwks = {"keys": [eval(self.token)["jwks_token"]]}
        payload = {
            "aud": modified_url.split("?")[0],
            "exp": datetime.utcnow() + timedelta(minutes=3),
            "iat": datetime.utcnow(),
            "iss": eval(self.token)["api_token"],
            "jti": uuid.uuid4().hex,
            "sub": "GET",
        }

        response = requests.get(
            modified_url,
            headers={
                "x-apex-jwt": jwt.encode(
                    payload,
                    get_key(jwks["keys"][0]),
                    headers={"alg": "ES256", "typ": "JWT", "kid": "dart"},
                )
            },
            verify=True,
        )

        return response

    def get_list_items(self):
        url_list_title = f"lists/{self.parameter.get('api_details').get('api_list_title')}"
        response = self.sharepoint_requests(url_list_title).json()
        list_id = response["id"]

        next_url = f"lists/{list_id}/items"
        while True:
            response = self.sharepoint_requests(next_url).json()
            temp_dict = response["value"].copy()
            for each in temp_dict:
                each["@odata.context"] = response["@odata.context"]
            self.list_of_items.extend(temp_dict)

            try:
                if next_url == response["@odata.nextLink"].replace(self.url_ms_base, ""):
                    self.print_verbose(
                        "previous next url and new next url is the same, suspected issue with API function, breaking loop"
                    )
                    break
                else:
                    next_url = response["@odata.nextLink"]
                    self.print_verbose("Getting next set of list of items")
            except:
                break
            else:
                next_url = next_url.replace(self.url_ms_base, "")

        self.print_verbose(f"Total list of items identified: {len(self.list_of_items)}")

    def filter_list_items(self):
        search_path = self.parameter.get("api_details").get("api_search_path").replace(" ", "%20")
        timestamp = self.time_interval
        self.filtered_parent = list(
            set(
                [
                    x["parentReference"]["id"]
                    for x in self.list_of_items
                    if x["lastModifiedDateTime"] >= timestamp
                    and x["webUrl"].find(search_path) != -1
                ]
            )
        )
        self.print_verbose(f"Total list of filtered parent: {len(self.filtered_parent)}")

    def get_child_items(self):
        for folder_id in self.filtered_parent:
            next_url = f"drive/items/{folder_id}/children"
            while True:
                response = self.sharepoint_requests(next_url).json()
                temp_dict = response["value"].copy()
                for each in temp_dict:
                    each["@odata.context"] = response["@odata.context"]
                self.list_of_child.extend(temp_dict)

                try:
                    if next_url == response["@odata.nextLink"].replace(self.url_ms_base, ""):
                        self.print_verbose(
                            "previous next url and new next url is the same, suspected issue with API function, breaking loop"
                        )
                        break
                    else:
                        next_url = response["@odata.nextLink"]
                except:
                    break
                else:
                    next_url = next_url.replace(self.url_ms_base, "")

        self.print_verbose(f"Total list of child items: {len(self.list_of_child)}")

    def filter_child_item(self):
        timestamp = self.time_interval
        filtered_list = []
        temp_list = [
            x
            for x in self.list_of_child
            if x["lastModifiedDateTime"] >= timestamp
            and x["parentReference"]["path"].find(
                self.parameter.get("api_details").get("api_search_path")
            )
            != -1
        ]
        for each in temp_list:
            try:
                each["@microsoft.graph.downloadUrl"]
                self.print_verbose("download url found, appending")
            except:
                self.print_verbose("download url not found, skipping")
            else:
                filtered_list.append(each)
        self.filtered_child = filtered_list

        self.print_verbose(f"Total list of filtered child: {len(self.filtered_child)}")

    def create_volume(self, metadata):
        output_path = metadata.get("output_path")
        for each_path in output_path:
            self.print_verbose(f"Creating Volume if not exist: {each_path}")
            each_path = each_path.split("/")
            spark.sql(
                f"CREATE VOLUME IF NOT EXISTS {self.project}_{self.env}.{each_path[0]}.{each_path[1]}"
            )

    def create_full_path(self, output_target, each_output_path, file_name):
        if output_target == "s3":
            full_path = f"s3://{each_output_path}/{file_name}"
        elif output_target == "volumes":
            full_path = os.path.join(
                f"/Volumes/{self.project}_{self.env}", each_output_path, file_name
            )
        return full_path

    def save_transformed_df(
        self,
        dataframe,
        output_target,
        output_save_mode,
        file_extension,
        each_output_path,
        file_name,
    ):
        self.print_verbose("Saving transformed Dataframe")

        if file_extension == "parquet":
            file_name = f"{file_name}.parquet"
        elif file_extension == "csv":
            file_name = f"{file_name}.csv"
        elif file_extension == "xlsx" or file_extension == "excel":
            file_name = f"{file_name}.xlsx"

        if output_save_mode == "appending":
            lastModifiedDateTime = (
                datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ").replace(":", "-")
            )
            file_name = self.append_datetime_to_filename(file_name, lastModifiedDateTime)
        self.print_verbose(file_name)

        full_path = self.create_full_path(output_target, each_output_path, file_name)
        self.print_verbose(full_path)

        if file_extension == "parquet":
            dataframe.to_parquet(full_path, index=False)
        elif file_extension == "csv":
            dataframe.to_csv(full_path, index=False)
        elif file_extension == "xlsx" or file_extension == "excel":
            dataframe.to_excel(full_path, index=False)

    def save_direct_file(
        self,
        output_path,
        output_target,
        output_save_mode,
        lastModifiedDateTime,
        parentReference,
        web_url,
        file_name,
    ):
        self.print_verbose("Saving direct file")
        if output_save_mode == "appending":
            file_name = self.append_datetime_to_filename(file_name, lastModifiedDateTime)
        self.print_verbose(file_name)

        for each_output_path in output_path:
            full_path = self.create_full_path(output_target, each_output_path, file_name)
            self.print_verbose(full_path)

            ### Download file using urllib into local cluster storage
            dbutils.fs.mkdirs("file:/tmp")
            urllib.request.urlretrieve(web_url, os.path.join("/tmp", file_name))

            ### Use dbutils to move files from either tmp, into a unity catalog volume
            dbutils.fs.mv(os.path.join("file:/tmp", file_name), full_path)

    def save_to_output(self, df_pandas=None):
        output_kwargs = self.parameter.get("output_format")

        for each_output_kwargs in output_kwargs:
            output_approach = each_output_kwargs.get("output_approach").lower()
            output_target = each_output_kwargs.get("output_target").lower()
            output_save_mode = each_output_kwargs.get("output_save_mode").lower()
            output_path = each_output_kwargs.get("output_path")

            if output_target == "volumes":
                self.create_volume(each_output_kwargs)

            if output_approach == "direct":
                for each in self.filtered_child:
                    web_url = each.get("@microsoft.graph.downloadUrl")
                    file_name = each.get("name")
                    lastModifiedDateTime = each.get("lastModifiedDateTime")
                    parentReference = each.get("parentReference")
                    self.save_direct_file(
                        output_path,
                        output_target,
                        output_save_mode,
                        lastModifiedDateTime,
                        parentReference,
                        web_url,
                        file_name,
                    )

            elif output_approach == "transformed":
                file_name = each_output_kwargs.get("output_file_name")
                file_extension = each_output_kwargs.get("output_file_type")

                for each_output_path in output_path:
                    self.save_transformed_df(
                        df_pandas,
                        output_target,
                        output_save_mode,
                        file_extension,
                        each_output_path,
                        file_name,
                    )


def main_SharePointOnline(verbose=False, **kwargs):
    sharepoint = SharePointOnline(verbose=verbose, **kwargs)
    sharepoint.get_list_items()
    sharepoint.filter_list_items()
    sharepoint.get_child_items()
    sharepoint.filter_child_item()
    return sharepoint
