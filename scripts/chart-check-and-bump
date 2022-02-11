#!/usr/bin/env python3


import argparse
import sys

from lib.charts import check_and_bump_all

parser = argparse.ArgumentParser(description=check_and_bump_all.__doc__)

if __name__ == "__main__":
    parser.parse_args()
    exit = check_and_bump_all()
    sys.exit(exit)
