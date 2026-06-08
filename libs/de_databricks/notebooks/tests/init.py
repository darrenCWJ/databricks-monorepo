# Databricks notebook source
import unittest

loader = unittest.TestLoader()
tests = loader.discover("tests", pattern="test_housekeeping.py")
runner = unittest.runner.TextTestRunner()
result = runner.run(tests)

assert result.errors == []
assert result.failures == []
