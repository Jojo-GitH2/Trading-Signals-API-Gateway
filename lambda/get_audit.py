import json
import boto3


def lambda_handler(event, context):

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("trading-signals-results")

    response = table.scan()
    # items = {"Items" : response["Items"]}
    items = response
    # TODO implement
    return {"statusCode": 200, "body": json.dumps(items)}
