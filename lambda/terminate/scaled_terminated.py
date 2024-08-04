import json
import boto3


def lambda_handler(event, context):
    instances = json.loads(event["body"])

    if not instances:
        return {"statusCode": 200, "body": json.dumps({"terminated": True})}

    ec2 = boto3.resource("ec2")
    for instance in instances:
        state = ec2.Instance(instance).state["Name"]
        if state != "terminated":
            return {"statusCode": 200, "body": json.dumps({"terminated": False})}
        else:
            # TODO implement
            return {"statusCode": 200, "body": json.dumps({"terminated": True})}
