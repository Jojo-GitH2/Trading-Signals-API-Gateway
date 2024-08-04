import boto3
from google.cloud import secretmanager


def terminate_ec2_instances():
    ec2 = boto3.resource("ec2")
    instances = ec2.instances.filter(
        Filters=[{"Name": "image-id", "Values": ["ami-0c101f26f147fa7fd"]}]
    )

    # Store all security group IDs before terminating the instances
    security_group_ids = set()  # Use a set to avoid duplicates
    for instance in instances:
        for sg in instance.security_groups:
            security_group_ids.add(sg["GroupId"])
    # print(security_group_ids)

    # Terminate all instances
    for instance in instances:
        instance.terminate()

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


def terminate_dynamodb_tables(table_name):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    table.delete()


# This takes too long to run because the json file is too large, about 320MB so I hard-coded the price to the function in main.py
# def get_ec2_price(region_name="us-east-1", instance_type="t2.micro"):
#     url = f"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{region_name}/index.json"
#     response = requests.get(url)
#     pricing = json.loads(response.text)

#     for product in pricing["products"].values():
#         if (
#             product["productFamily"] == "Compute Instance"
#             and product["attributes"]["instanceType"] == instance_type
#         ):
#             sku = product["sku"]
#             price_dimensions = (
#                 pricing["terms"]["OnDemand"][sku]
#                 .values()[0]["priceDimensions"]
#                 .values()[0]
#             )
#             price_per_hour = price_dimensions["pricePerUnit"]["USD"]
#             return price_per_hour
#     return None

# def get_ec2_price(region_name="us-east-1", instance_type="t2.micro"):


def get_secret(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
