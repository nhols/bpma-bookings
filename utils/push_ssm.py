#!/usr/bin/env python3

import boto3
from dotenv import dotenv_values

from src import PATH


def main():
    ssm = boto3.client("ssm")

    for key, value in dotenv_values().items():
        if not (key and value):
            continue
        param_name = f"{PATH}{key}"
        param_type = "SecureString"
        print(param_name)
        ssm.put_parameter(Name=param_name, Value=value, Type=param_type, Overwrite=True)
        print(f"Created/Updated parameter: {param_name}")

    print("All parameters pushed successfully")


if __name__ == "__main__":
    main()
