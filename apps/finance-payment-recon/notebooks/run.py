# Databricks notebook source
dbutils.widgets.text("catalog", "cdo_dev")
catalog = dbutils.widgets.get("catalog")
from finance_payment_recon.job import run
run(catalog)
