import json
import boto3


def lambda_handler(event, context):
    # TODO implement
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("trading-signals-results")

    response = table.scan()
    if response["Items"]:
        latest = sorted(response["Items"], key=lambda x: x["timestamp"], reverse=True)[
            0
        ]

        return {
            "statusCode": 200,
            "body": json.dumps({"time": latest["time"], "cost": latest["cost"]}),
        }
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "No Items found"})}
