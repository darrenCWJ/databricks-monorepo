# token will expire in

#!pip install --index-url https://nexus.ship.gov.sg/repository/pypi-proxy/simple pycryptodome
#!pip install pycryptodome
import base64
import json
import sys
import time
from base64 import b64decode

import requests
import urllib3
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from pyspark.dbutils import DBUtils
from pyspark.sql import SparkSession
from urllib3._collections import HTTPHeaderDict


def token():
    spark = SparkSession.builder.getOrCreate()
    dbutils = DBUtils(spark)

    path = "/Workspace/Repos/jay_ang@tech.gov.sg/inf_wd/"
    if path not in sys.path:
        sys.path.append(path)

    f = open("/Workspace/Repos/jay_ang@tech.gov.sg/inf_wd/config.json")
    config = json.load(f)
    header = '{"alg":"RS256","typ":"JWT"}'
    claimTemplate = '\'{\'"iss": "", "sub": "", "aud": "", "exp": ""\'}\''
    token_bytes = header.encode("utf-8")
    token = base64.urlsafe_b64encode(token_bytes) + b"."
    current_time = round(time.time()) + 300
    json_data = {}
    json_data["iss"] = config["client_id"]
    json_data["sub"] = config["user_id"]
    json_data["aud"] = "wd"
    json_data["exp"] = str(current_time)
    payload = json.dumps(json_data)
    payload_bytes = payload.encode("utf-8")
    token = token + base64.urlsafe_b64encode(payload_bytes)
    tokenstring = token.decode("utf-8")

    key = dbutils.secrets.get(scope="dart_wd", key="private_key")

    keyDER = b64decode(key)
    keyPub = RSA.importKey(keyDER)

    tokenstring = token.decode("utf-8")
    tokenstring = tokenstring.replace("=", "")
    token = tokenstring.encode()
    h = SHA256.new(token)
    signature = PKCS1_v1_5.new(keyPub).sign(h)
    result = base64.urlsafe_b64encode(signature).decode()

    token = token + b"." + result.encode(encoding="UTF-8")
    tokenstring = token.decode("utf-8")
    tokenstring = tokenstring.replace("=", "")

    formdata = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": tokenstring,
    }
    api_url = config["api_url"]
    http = urllib3.PoolManager()
    timeout = urllib3.Timeout(connect=900, read=900)
    headers = HTTPHeaderDict()
    headers.add("User-Agent", "DART WD API 2")
    headers.add("Content-Type", "application/x-www-form-urlencoded")
    response = requests.post(api_url, data=formdata, headers=headers)
    token = json.loads(response.text)["access_token"]
    return token
