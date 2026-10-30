"""Loader for config/identity.json.

Public identity lives in exactly one file. Scripts import from here rather
than hardcoding a handle, so changing the handle is a one-line edit in
config/identity.json and nothing else.
"""

import json
import os

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "identity.json")

REQUIRED = ("display_name", "x_handle", "substack_url")


def load_identity(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise SystemExit("%s is missing: %s" % (path, ", ".join(missing)))
    return {k: data[k] for k in REQUIRED}


def credit_line(identity=None):
    """The one-line attribution used in footers on public outputs."""
    i = identity or load_identity()
    return "%s  %s  %s" % (
        i["display_name"], i["x_handle"],
        i["substack_url"].replace("https://", ""))


if __name__ == "__main__":
    for k, v in load_identity().items():
        print("%-14s %s" % (k, v))
    print("\ncredit line:  %s" % credit_line())
