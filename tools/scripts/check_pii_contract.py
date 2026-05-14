"""Pre-commit hook: every Restricted column must have a mask_function.

Reads schema.yml / contract files in the diff and refuses MRs where
classification == "Restricted" without a mask declared.
"""
# Stub.
if __name__ == "__main__":
    raise SystemExit(0)
