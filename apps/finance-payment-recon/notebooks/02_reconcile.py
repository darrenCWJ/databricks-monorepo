# Databricks notebook source
dbutils.widgets.text("catalog", "cdo_dev")
catalog = dbutils.widgets.get("catalog")

from finance_payment_recon.reconcile import reconcile_payments
reconcile_payments(catalog)
