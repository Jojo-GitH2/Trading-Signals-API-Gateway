import json
import boto3


def lambda_handler(event, context):
    # Parse input parameters from event
    instance_id = event["instance_id"]

    # Initialize SDK
    ssm = boto3.client("ssm")

    # Send command to delete data.json
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": ["rm -f /home/ec2-user/data.json"]},
    )

    return {"statusCode": 200, "body": json.dumps("data.json deleted successfully")}
