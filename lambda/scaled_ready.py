import json
import boto3


def lambda_handler(event, context):

    data = json.loads(event["body"])
    instances = data.get("instances")

    ec2 = boto3.client("ec2")
    response = ec2.describe_instance_status(InstanceIds=instances)
    for instance in response["InstanceStatuses"]:
        if (
            instance["InstanceState"]["Name"] != "running"
            or instance["InstanceStatus"]["Status"] != "ok"
        ):
            return {"statusCode": 200, "body": json.dumps({"warm": False})}
    else:
        return {"statusCode": 200, "body": json.dumps({"warm": True})}
