import json
import boto3
import base64


def lambda_handler(event, context):
    # Parse input parameter
    data = json.loads(event["body"])
    s = data.get("s")
    r = int(data.get("r"))

    # Read the user data script
    with open("user_data.sh", "r") as f:
        user_data = f.read()

    user_data_encoded = base64.b64encode(user_data.encode()).decode()

    instance_ids = []

    if s.lower() == "ec2":
        # Setup resources
        dynamodb = boto3.resource("dynamodb")
        table_name = "trading-signals-results"

        # Check if the DynamoDB table exists
        try:
            table = dynamodb.Table(table_name)
            table.table_status
        except dynamodb.meta.client.exceptions.ResourceNotFoundException:
            # If the table does not exist, create it
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "timestamp", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )

        ec2_client = boto3.client("ec2")
        security_group_name = "TradingSignals"
        security_group_description = "Trading Signals Security Group"

        # Check if the security group already exists
        response = ec2_client.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [security_group_name]}]
        )
        if response["SecurityGroups"]:
            security_group_id = response["SecurityGroups"][0]["GroupId"]

        # If the security group does not exist, create it
        elif not response["SecurityGroups"]:
            response = ec2_client.create_security_group(
                GroupName=security_group_name,
                Description=security_group_description,
            )
            security_group_id = response["GroupId"]

            # Authorize inbound SSH traffic on port 22
            ec2_client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 443,
                        "ToPort": 443,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 5000,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                ],
            )

        instances_running = ec2_client.describe_instances(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": ["running", "pending"],
                }
            ]
        )
        count = sum(
            len(reservation["Instances"])
            for reservation in instances_running["Reservations"]
        )

        if count < r:
            response = ec2_client.run_instances(
                ImageId="ami-0c101f26f147fa7fd",
                InstanceType="t2.micro",
                MaxCount=int(abs(r - count)),
                MinCount=int(abs(r - count)),
                KeyName="vockey",
                UserData=user_data_encoded,
                SecurityGroupIds=[security_group_id],
                IamInstanceProfile={"Name": "LabInstanceProfile"},
            )
            instance_ids = [
                instance["InstanceId"] for instance in response["Instances"]
            ]

            if count > 0:
                # Add IDs of the existing instances to the list
                instance_ids.extend(
                    instance["InstanceId"]
                    for reservation in instances_running["Reservations"]
                    for instance in reservation["Instances"]
                )
        else:
            instance_ids = [
                instance["InstanceId"]
                for reservation in instances_running["Reservations"]
                for instance in reservation["Instances"]
            ]

    # Return response
    return {"statusCode": 200, "body": json.dumps({"instance_ids": instance_ids})}
    # return {
    #     'statusCode' : 200,
    #     'body' : json.dumps(data)
    # }
