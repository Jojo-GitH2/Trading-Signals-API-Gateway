import json
import boto3


def lambda_handler(event, context):

    instances = json.loads(event["body"])

    lambda_client = boto3.client("lambda")

    for instance_id in instances:

        # Input Parameters for the reset Lambda function

        input_params = {"instance_id": instance_id}

        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName="reset",
            InvocationType="Event",
            Payload=json.dumps(input_params),
        )

    # TODO implement
    return {"statusCode": 200, "body": json.dumps("Done")}
