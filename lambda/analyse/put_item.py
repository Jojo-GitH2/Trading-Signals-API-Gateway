import json
import boto3


def lambda_handler(event, context):
    # data = json.loads(event["body"])
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("trading-signals-results")

    table.put_item(Item=event)

    # print(event)
    # TODO implement
    return {"statusCode": 200, "body": json.dumps("Done")}
