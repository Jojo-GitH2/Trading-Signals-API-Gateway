import json
import boto3


def lambda_handler(event, context):

    data = json.loads(event["body"])
    h = data.get(
        "h"
    )  # the length of price history from which to generate mean and standard deviation
    d = data.get(
        "d"
    )  # the number of data points (shots) to generate in each r for calculating risk via simulated returns
    t = data.get("t")
    p = data.get(
        "p"
    )  # the number of data points (shots) to generate in each r for calculating risk via simulated returns
    instances = data.get("instances")

    if instances:
        lambda_client = boto3.client("lambda")
        input_params = {"h": h, "d": d, "t": t, "p": p}

        for instance in instances:
            input_params["instance"] = instance
            response = lambda_client.invoke(
                FunctionName="risk_analysis",
                InvocationType="Event",
                Payload=json.dumps(input_params),
            )
    # TODO implement
    return {"statusCode": 200, "body": json.dumps(data)}
