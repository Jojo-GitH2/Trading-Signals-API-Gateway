import json
import boto3
import datetime
import time


def lambda_handler(event, context):
    # Parse input parameters from event
    h = int(event["h"])
    d = int(event["d"])
    t = event["t"]
    p = int(event["p"])
    instance_id = event["instance_id"]

    # Initialize SDK

    ssm = boto3.client("ssm")

    command = f"cd /home/ec2-user && python3 risk_analysis.py {h} {d} {t} {p}"

    # Send commands to ec2 instance

    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
            "commands": [command],
        },
    )

    return {"statusCode": 200, "body": json.dumps({"Result": "ok"})}


# Test Event
# {
#     "h": "101",
#     "d": "10000",
#     "t": "sell",
#     "p": "7",
#     "s": "ec2",
#     "r": 1,
#     "table_name": "trading-signals-results",
#     "instance_id": "i-0eeb3eec242dc444b",
# }
