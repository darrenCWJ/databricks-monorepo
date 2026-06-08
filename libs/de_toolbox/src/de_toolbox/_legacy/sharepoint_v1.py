import json
import os
import re
import xml.etree.ElementTree as et
from collections import Counter

import pandas as pd
import requests
from databricks.sdk.runtime import *
from requests_ntlm import HttpNtlmAuth

from de_toolbox.catalog import get_catalog, get_repo_path


class SharePointConnector:
    def __init__(self, username, password, ca_cert_path, site_url, catalog, verbose=False):
        self.verbose = verbose
        self.session = self.create_sharepoint_session(username, password, ca_cert_path)
        self.site_url = site_url
        self.catalog = catalog
        self.api = {
            "list": "_api/web/Lists/GetByTitle",
            "doc": "_api/web/GetFileByServerRelativeUrl",
        }
        self.namespaces = {
            "atom": "http://www.w3.org/2005/Atom",
            "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
            "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
        }

    def print_verbose(self, message):
        if self.verbose:
            print(message)

    def create_sharepoint_session(self, username, password, ca_cert_path):
        session = requests.Session()
        session.auth = HttpNtlmAuth(username, password)
        session.verify = ca_cert_path
        return session

    def get_all_lists(self):
        endpoint = f"{self.site_url}/_api/web/lists?$select=Title"
        headers = {
            "Accept": "application/json;odata=verbose",
            "Content-Type": "application/json;odata=verbose",
        }
        response = self.session.get(endpoint, headers=headers)

        if response.status_code != 200:
            print(f"Failed to retrieve lists. Status code: {response.status_code}")
            return []

        data = response.json()
        return [list_item["Title"] for list_item in data["d"]["results"]]

    def clean_and_uniquify_df_columns(self, df):
        def clean_name(col):
            # Title each word's first letter
            titled = col.title()
            # Remove invalid characters
            cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", titled)
            # Remove extra spaces and replace spaces with nothing
            final = re.sub(r"\s+", "", cleaned).strip()
            return final

        # Clean all column names
        cleaned_columns = [clean_name(col) for col in df.columns]

        # Handle duplicates
        column_counts = Counter(cleaned_columns)
        unique_columns = []
        seen_counts = {}

        self.print_verbose(f"Counter Columns: {column_counts}")

        for col in cleaned_columns:
            if column_counts[col] > 1:
                count = seen_counts.get(col, 0) + 1
                seen_counts[col] = count
                unique_columns.append(f"{col}{count}")
            else:
                unique_columns.append(col)

        self.print_verbose(f"Unique Columns: {unique_columns}")

        # Create a mapping from old to new column names
        column_mapping = dict(zip(df.columns, unique_columns))

        # If you want to see the mapping:
        for old, new in column_mapping.items():
            self.print_verbose(f"{old} -> {new}")

        df.columns = unique_columns

        return df, column_mapping

    def sharepoint_connector(self, api_meta, field_transformations):
        name = api_meta.pop("name", None)
        api_type = api_meta.pop("type", "list")

        select_fields = api_meta.get("select", "").split(",")
        expand_fields = api_meta.get("expand", "").split(",")

        self.print_verbose(f"Initial select fields: {select_fields}")
        self.print_verbose(f"Initial expand fields: {expand_fields}")

        for field, config in field_transformations.items():
            if config.get("expand", False):
                expand_fields.append(field)
                select_fields.extend([f"{field}/{subfield}" for subfield in config["select"]])

        api_meta["select"] = ",".join(filter(None, select_fields))
        api_meta["expand"] = ",".join(filter(None, expand_fields))

        self.print_verbose(f"Modified select fields: {select_fields}")
        self.print_verbose(f"Modified expand fields: {expand_fields}")

        all_data = []
        next_url = f"{self.site_url}/{self.api['list']}('{name}')/items?"
        next_url += "".join([f"${key}={api_meta[key]}&" for key in api_meta])

        while next_url:
            response = self.session.get(next_url)
            if response.status_code != 200:
                print(f"Failed to retrieve data. Status code: {response.status_code}")
                return None

            self.print_verbose(f"Content-Type: {response.headers.get('Content-Type')}")

            all_data.append(response.content)

            root = et.fromstring(response.content)
            next_link = root.find(".//{*}link[@rel='next']")
            next_url = next_link.attrib["href"] if next_link is not None else None

        self.print_verbose(f"Number of requests: {len(all_data)}")

        if api_type == "list":
            return self.process_list_data(name, all_data, field_transformations)
        else:
            return self.process_document_data(root)

    def process_list_data(self, name, all_data, field_transformations):
        fields_endpoint = f"{self.site_url}/_api/web/Lists/GetByTitle('{name}')/fields"
        fields_response = self.session.get(fields_endpoint)
        if fields_response.status_code != 200:
            print(f"Failed to retrieve fields. Status code: {fields_response.status_code}")
            return None
        fields = et.fromstring(fields_response.content)

        subtree = fields.findall(".//{*}properties")
        mapping = {}
        field_types = {}
        for child in subtree:
            internal_name = None
            display_name = None
            field_type = None
            for ele in child:
                tag = ele.tag.split("}")[-1]
                if tag == "EntityPropertyName":
                    internal_name = ele.text
                elif tag == "Title":
                    display_name = ele.text
                elif tag == "FieldType":
                    field_type = ele.text
            if internal_name and display_name:
                mapping[internal_name] = display_name
                field_types[internal_name] = field_type

        self.print_verbose(f"Length of mapping: {len(mapping)}")
        self.print_verbose(f"Length of field_types: {len(field_types)}")

        table = []

        for each_response in all_data:
            root = et.fromstring(each_response)
            entries = root.findall("atom:entry", self.namespaces)

            for entry in entries:
                item = {}

                content = entry.find("atom:content/m:properties", self.namespaces)
                if content is not None:
                    for prop in content:
                        tag = prop.tag.split("}")[-1]
                        if "m:null" in prop.attrib and prop.attrib["m:null"] == "true":
                            item[tag] = None
                        elif "m:type" in prop.attrib:
                            if prop.attrib["m:type"] == "Edm.Int32":
                                item[tag] = int(prop.text) if prop.text is not None else None
                            elif prop.attrib["m:type"] == "Edm.DateTime":
                                item[tag] = prop.text
                            elif prop.attrib["m:type"] == "Edm.Boolean":
                                item[tag] = prop.text.lower() == "true"
                            elif prop.attrib["m:type"] == "Edm.Guid":
                                item[tag] = prop.text
                            else:
                                item[tag] = prop.text
                        else:
                            item[tag] = prop.text

                for field, config in field_transformations.items():
                    if config.get("expand", False):
                        current_field = entry.find(
                            f'atom:link[@title="{field}"]/m:inline/atom:entry/atom:content/m:properties',
                            self.namespaces,
                        )
                        if current_field is not None:
                            subfield_rename = config.get("rename", {})
                            for each_subfield in config["select"]:
                                each_subfield_column = subfield_rename.get(
                                    each_subfield, f"{field}_{each_subfield}"
                                )
                                item[each_subfield_column] = (
                                    current_field.find(f"d:{each_subfield}", self.namespaces).text
                                    if current_field.find(f"d:{each_subfield}", self.namespaces)
                                    is not None
                                    else None
                                )

                if item:
                    table.append(item)

        df = pd.DataFrame(table)
        df.rename(columns=mapping, inplace=True)
        df, column_mapping = self.clean_and_uniquify_df_columns(df)
        return df

    def process_document_data(self, root):
        files = {}
        subtree = root.findall(".//{*}ServerRelativeUrl")
        for ele in subtree:
            endpoint = f"{self.site_url}/{self.api['doc']}('{ele.text}')/$value"
            file_response = self.session.get(endpoint)
            if file_response.status_code == 200:
                files[ele.text.split("/")[-1]] = file_response.content
            else:
                print(
                    f"Failed to download file {ele.text}. Status code: {file_response.status_code}"
                )
        return files

    def save_pandas_df_to_volume(self, df, volume_path, file_name):
        target_path = f"{volume_path}/{file_name}.parquet"
        df.to_parquet(target_path, index=False)
        print(f"Files saved to {target_path}")

    def clean_path(self, download_path):
        return download_path.strip().strip("//")

    def get_first_path_element(self, path):
        elements = path.split("/")
        non_empty_elements = [elem for elem in elements if elem]
        return non_empty_elements[0] if non_empty_elements else ""

    def get_sharepoint_data(
        self, data_type, metadata_name, download_path, api_meta, field_transformations
    ):
        try:
            response = self.session.get(self.site_url)
            if response.status_code == 200:
                print(f"Successfully connected to {self.site_url}")
            else:
                print(f"Failed to connect to {self.site_url}. Status code: {response.status_code}")
                return None
        except requests.RequestException as e:
            print(f"Error connecting to {self.site_url}: {e}")
            return None

        data = self.sharepoint_connector(api_meta, field_transformations)

        download_path = self.clean_path(download_path)
        volume_path = f"/Volumes/{self.catalog}/bronze/{download_path}"
        volume_name = self.get_first_path_element(download_path)

        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.bronze")
            spark.sql(f"CREATE VOLUME IF NOT EXISTS {self.catalog}.bronze.{volume_name}")
        except:
            print("Catalog, Schema, Volume Creation Error")

        if data_type == "list":
            self.save_pandas_df_to_volume(data, volume_path, download_path)
        elif data_type != "list":
            if isinstance(data, dict) and data:
                for filename, content in data.items():
                    file_path = os.path.join(download_path, filename)
                    with open(file_path, "wb") as file:
                        file.write(content)
                    print(f"Downloaded: {filename}")
                print(f"All files have been downloaded to {download_path}")
            else:
                print("No files available to download.")
                return None

        return data

    def sharepoint_main(self, metadata, reload_sharepoint, first_load):
        sharepoint_lists = metadata.get("sharepoint_lists", [])

        for each_list in sharepoint_lists:
            data_type = each_list.get("api_meta").get("type", None)
            metadata_name = each_list.get("api_meta").get("name", None)
            download_path = each_list.get("output_volume", None)
            api_meta = each_list.get("api_meta", None)
            field_transformations = each_list.get("field_transformations", None)

            self.print_verbose(f"Processing {data_type}: {metadata_name}")

            if not data_type or not metadata_name:
                print(
                    f"Skipping Processing - data_type: {data_type}, metadata_name: {metadata_name} errors"
                )
            else:
                list_data = self.get_sharepoint_data(
                    data_type, metadata_name, download_path, api_meta, field_transformations
                )


def run_sharepoint(
    _spark,
    project,
    metadata_name,
    env,
    reload_sharepoint=False,
    first_load=False,
    verbose=False,
    debug=None,
):
    global spark
    if project == "toolbox":
        catalog = get_catalog("test", env)
    else:
        catalog = get_catalog(project, env)

    base_path = get_repo_path(project, debug, "sharepoint")
    metadata_path = f"{base_path}/{metadata_name}.json"

    with open(metadata_path) as read_file:
        metadata = json.load(read_file)

    # Assign spark
    spark = _spark

    # Convert param to True/False
    reload_sharepoint = spark.sql(f"select '{reload_sharepoint}' is true").collect()[0][0]
    first_load = spark.sql(f"select '{first_load}' is true").collect()[0][0]
    verbose = spark.sql(f"select '{verbose}' is true").collect()[0][0]

    # Extract SharePoint connection details from metadata
    secret_scope = metadata.get("secret_scope")
    username_key = metadata.get("secret_username")
    password_key = metadata.get("secret_password")
    username = dbutils.secrets.get(secret_scope, username_key)
    password = dbutils.secrets.get(secret_scope, password_key)
    ca_file_name = metadata.get("ca_cert_path")
    ca_cert_path = f"/Volumes/{catalog}/bronze/system_input/sharepoint/{ca_file_name}"
    sharepoint_url = metadata.get("sharepoint_url")

    # Initialize the SharePointConnector
    connector = SharePointConnector(
        username, password, ca_cert_path, sharepoint_url, catalog, verbose
    )

    # Run the SharePoint ingestion
    connector.sharepoint_main(metadata, reload_sharepoint, first_load)
