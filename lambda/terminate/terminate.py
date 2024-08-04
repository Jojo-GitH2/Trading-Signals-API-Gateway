import json
import boto3

# import helper
import threading


def lambda_handler(event, context):
    # response = helper.terminate_ec2_instances()

    thread = threading.Thread(target=terminate_ec2_instances())
    thread.start()

    # terminate_ec2_instances()
    # TODO implement
    return {"statusCode": 200, "body": json.dumps("Done")}


def terminate_dynamodb_tables(table_name):
    dynamodb = boto3.resource("dynamodb")
    try:
        table = dynamodb.Table(table_name)
        table.table_status
        table.delete()
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        pass


def terminate_ec2_instances():
    ec2 = boto3.resource("ec2")
    instances = ec2.instances.filter(
        Filters=[{"Name": "image-id", "Values": ["ami-0c101f26f147fa7fd"]}]
    )

    # Store all security group IDs before terminating the instances
    security_group_ids = set()  # Use a set to avoid duplicates
    for instance in instances:
        sg = instance.security_groups
        # security_group_ids.add(sg["GroupId"])
        if len(sg) != 0:
            security_group_ids.add(sg[0]["GroupId"])
            break
    # Terminate all instances
    instances.terminate(DryRun=False)

    table_name = "trading-signals-results"
    terminate_dynamodb_tables(table_name)

    # Wait for all instances to be terminated
    for instance in instances:
        instance.wait_until_terminated()

    # After all instances have been terminated, delete the Security Group
    for sg_id in security_group_ids:
        # Now delete the security group
        ec2.SecurityGroup(sg_id).delete()

    # Delete the VPC if it's not the default one
    vpc_ids = set()  # Use a set to avoid duplicates
    for instance in instances:
        if instance.vpc_id and instance.vpc_id != "default":
            vpc_ids.add(instance.vpc_id)

    for vpc_id in vpc_ids:
        ec2.Vpc(vpc_id).delete()
