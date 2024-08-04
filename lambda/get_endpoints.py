import json
import boto3


def lambda_handler(event, context):
    data = json.loads(event["body"])
    instances = data.get("instances")
    ec2 = boto3.resource("ec2")
    endpoints = {}
    count = 0

    for instance in instances:
        instance = ec2.Instance(instance)
        count += 1

        endpoints[f"endpoint {count}"] = (
            f"http://{instance.public_dns_name}:5000/data.json"
        )
    # TODO implement
    return {"statusCode": 200, "body": json.dumps(endpoints)}
