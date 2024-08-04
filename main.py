from flask import Flask, request, jsonify, render_template
import boto3
from boto3.dynamodb.conditions import Key
import json
import helper
import os
import time
import base64
import numpy as np
import requests
import datetime
import threading

# import risk_analysis

app = Flask(__name__)

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Run one of this on the command line before running the code below:
# To create a secret with the AWS credentials in the Google Secret Manager
# gcloud secrets create aws-credentials  --data-file=C:\Users\Lawal\.aws\credentials --project=trading-signals-418515

# To Update the secret with the AWS credentials in the Google Secret Manager
# gcloud secrets versions add aws-credentials --data-file=C:\Users\Lawal\.aws\credentials --project=trading-signals-418515

if os.getenv("GAE_ENV", "").startswith("standard"):
    # Authenticate with AWS
    aws_credentials = helper.get_secret(
        project_id="trading-signals-418515", secret_id="aws-credentials"
    )

    try:
        lines = aws_credentials.split("\n")
        if len(lines) < 4:
            raise ValueError("Invalid AWS credentials format")

        aws_access_key_id = lines[1].split("=")[1].strip()
        aws_secret_access_key = lines[2].split("=")[1].strip()
        aws_session_token = lines[3].split("=")[1].strip()

    except IndexError:
        print("Error: AWS credentials file is not in the expected format.")
    except ValueError as ve:
        print(f"Error: {ve}")

    # Configure boto3 with your AWS credentials
    boto3.setup_default_session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )

warmup_state = {
    "warm": False,
    "service": None,
    "terminated": True,
    "warmup_time": 0,
    "scale": 0,
    "cost": 0.0,
    "instances": [],
}

table_name = "trading-signals-results"


results = {}


@app.errorhandler(404)
def page_not_found(e):
    return jsonify(error=str(e)), 404


@app.route("/", methods=["GET"])
def home():
    # This is a simple home page, also doubles as a description of the API
    return render_template("index.html")


@app.route("/warmup", methods=["POST"])
def warmup():
    try:
        # Get the input parameters
        data = request.get_json()
        s = data.get("s")
        r = int(data.get("r"))

        # Store the service in the warmup_state
        warmup_state["service"] = s
        warmup_state["scale"] = r
        with open("user_data.sh", "r") as f:
            user_data = f.read()
        user_data_encoded = base64.b64encode(user_data.encode()).decode()

        instances_ids = []

        start_time = time.time()
        if s.lower() == "ec2":
            # Setup resources
            # ssm = boto3.client("ssm")
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
                    # {
                    #     "IpProtocol": "tcp",
                    #     "FromPort": 80,
                    #     "ToPort": 80,
                    #     "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    # },
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

        # table.wait_until_exists()
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
            instances_ids = [
                instance["InstanceId"] for instance in response["Instances"]
            ]

            if count > 0:
                # Add IDs of the existing instances to the list
                instances_ids.extend(
                    instance["InstanceId"]
                    for reservation in instances_running["Reservations"]
                    for instance in reservation["Instances"]
                )
        else:
            instances_ids = [
                instance["InstanceId"]
                for reservation in instances_running["Reservations"]
                for instance in reservation["Instances"]
            ]

        end_time = time.time()
        warmup_state["warmup_time"] = end_time - start_time

        if instances_ids != list():
            warmup_state["warm"] = True
            warmup_state["terminated"] = False
            warmup_state["instances"] = instances_ids
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify({"result": "ok"})


@app.route("/scaled_ready", methods=["GET"])
def scaled_ready():
    if len(warmup_state["instances"]) == 0:
        return jsonify({"warm": False})
    ec2 = boto3.client("ec2")
    response = ec2.describe_instance_status(InstanceIds=warmup_state["instances"])
    for instance in response["InstanceStatuses"]:
        if (
            instance["InstanceState"]["Name"] != "running"
            or instance["InstanceStatus"]["Status"] != "ok"
        ):
            warmup_state["warm"] = False
            break
    else:
        warmup_state["warm"] = True

    return jsonify({"warm": warmup_state["warm"]})


@app.route("/get_warmup_cost", methods=["GET"])
def get_warmup_cost():
    if not warmup_state["warm"]:
        return jsonify({"cost": warmup_state["cost"]})
    if warmup_state["service"] == "ec2":
        price_per_instance = 0.0116 / 3600  # Price per instance per second
        price_dynamodb = 1.25 / 730 / 60 / 60  # Price per second
        instance_cost = (
            price_per_instance * warmup_state["scale"] * warmup_state["warmup_time"]
        )
        dynamodb_cost = price_dynamodb * warmup_state["warmup_time"]
    warmup_state["cost"] = f"${instance_cost + dynamodb_cost:.5f}"
    return jsonify(
        {
            "billable_time": f'{round(warmup_state["warmup_time"], 2)} seconds',
            "cost": warmup_state["cost"],
        }
    )


@app.route("/get_endpoints", methods=["GET"])
def get_endpoints():
    ec2 = boto3.resource("ec2")
    endpoints = {}
    count = 0
    for instances in warmup_state["instances"]:
        instance = ec2.Instance(instances)
        count += 1
        endpoints[f"endpoint {count}"] = (
            f"http://{instance.public_dns_name}:5000/data.json"
        )
    return jsonify(
        endpoints,
    )  # Attached :5000/data.json to the end of the public dns name to see results of individual instances


@app.route("/analyse", methods=["POST"])
def analyse():
    data = request.get_json()
    h = data.get(
        "h"
    )  # the length of price history from which to generate mean and standard deviation
    d = data.get(
        "d"
    )  # the number of data points (shots) to generate in each r for calculating risk via simulated returns
    t = data.get("t")
    p = data.get(
        "p"
    )  # the number of data points (shots) to generate in each r for calculating risk via simulated returns
    if warmup_state["service"].lower() == "ec2":
        lambda_client = boto3.client("lambda")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        instances = warmup_state["instances"]

        # Input Parameters for the Lambda function
        input_params = {
            "h": h,
            "d": d,
            "t": t,
            "p": p,
        }

        # Invoke the Lambda function
        for instance_id in instances:
            input_params["instance_id"] = instance_id
            response = lambda_client.invoke(
                FunctionName="risk_analysis",
                InvocationType="Event",
                Payload=json.dumps(input_params),
            )

        time.sleep(5)

        endpoints = get_endpoints().get_json()
        execution_times = [
            requests.get(url).json()["execution_time"] for url in endpoints.values()
        ]
        execution_time = sum(execution_times) / len(execution_times)
        total_time = execution_time * len(execution_times)

        averages = get_avg_vars9599().get_json()

        table.put_item(
            Item={
                "timestamp": datetime.datetime.now().isoformat(),
                "s": warmup_state["service"],
                "r": warmup_state["scale"],
                "h": h,
                "d": d,
                "t": t,
                "p": p,
                "av95": str(averages["var95"]),
                "av99": str(averages["var99"]),
                "profit_loss": str(get_tot_profit_loss().get_json()["profit_loss"]),
                "time": str(f"{execution_time:.5f} seconds"),
                "cost": str(f"${total_time * 0.0116:.5f}"),
            }
        )

        return jsonify({"result": "ok"})


@app.route("/get_sig_vars9599", methods=["GET"])
def get_sig_vars9599():
    # Initialize the results for the VaR values
    var95 = []
    var99 = []
    endpoints = get_endpoints().get_json()

    # Fetch data.json from each endpoint
    for url in endpoints.values():
        response = requests.get(url)
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            return jsonify({"var95": [], "var99": []})

        var95.append(data["var95"])
        var99.append(data["var99"])

    # Convert to numpy arrays
    var95 = np.array(var95)
    var99 = np.array(var99)

    #  Calculate average across parallel computations per index
    var95 = list(np.mean(var95, axis=0))
    var99 = list(np.mean(var99, axis=0))
    return jsonify({"var95": var95, "var99": var99})


@app.route("/get_avg_vars9599", methods=["GET"])
def get_avg_vars9599():
    try:
        vaRs_9599 = get_sig_vars9599().get_json()
        avg_var95 = sum(vaRs_9599["var95"]) / len(vaRs_9599["var95"])
        avg_var99 = sum(vaRs_9599["var99"]) / len(vaRs_9599["var99"])
    except (requests.exceptions.JSONDecodeError, ZeroDivisionError):
        return jsonify({"var95": "0.0", "var99": "0.0"})
    return jsonify({"var95": avg_var95, "var99": avg_var99})


@app.route("/get_sig_profit_loss", methods=["GET"])
def get_sig_profit_loss():
    endpoints = get_endpoints().get_json()
    try:
        profit_loss = []
        # Fetch data.json from each endpoint
        for url in endpoints.values():
            response = requests.get(url)
            data = response.json()
            profit_loss.extend(data["profit_loss"])
            break
    except requests.exceptions.JSONDecodeError:
        return jsonify({"profit_loss": []})

    return jsonify({"profit_loss": profit_loss})


@app.route("/get_tot_profit_loss", methods=["GET"])
def get_tot_profit_loss():
    profit_loss = get_sig_profit_loss().get_json()["profit_loss"]
    total_profit_loss = sum(profit_loss)
    return jsonify({"profit_loss": total_profit_loss})


@app.route("/get_time_cost", methods=["GET"])
def get_time_cost():
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Scam the DynamoDB table for the latest results
    response = table.scan()

    if response["Items"]:
        # Sort the items by timestamp in descending order and get the latest item
        latest = sorted(response["Items"], key=lambda x: x["timestamp"], reverse=True)[
            0
        ]
        return jsonify(time=latest["time"], cost=latest["cost"])
    else:
        return jsonify(error="No items found"), 404


@app.route("/get_chart_url", methods=["GET"])
def get_chart_url():
    # Fetch 95% and 99% VaR values
    sig_vars9599 = get_sig_vars9599().get_json()
    avg_vars9599 = get_avg_vars9599().get_json()

    # Prepare data for the chart
    var95_values = ",".join(map(str, sig_vars9599["var95"]))
    var99_values = ",".join(map(str, sig_vars9599["var99"]))
    avg_var95_values = ",".join(
        [str(avg_vars9599["var95"])] * len(sig_vars9599["var95"])
    )
    avg_var99_values = ",".join(
        [str(avg_vars9599["var99"])] * len(sig_vars9599["var99"])
    )

    # Generate the chart URL
    chart_url = f"https://image-charts.com/chart?cht=lc&chs=750x350&chd=a:{var95_values}|{var99_values}|{avg_var95_values}|{avg_var99_values}&chxt=x,y&chxl=1:|%+risk+values&chtt=Risk+Values+Chart&chdl=Var95|Var99|Avg_Var95|Avg_Var99&chg=10,10"
    return jsonify({"url": chart_url})


@app.route("/get_audit", methods=["GET"])
def get_audit():
    # Fetch the results from the DynamoDB table
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response["Items"]
    return jsonify(items)


@app.route("/reset", methods=["GET"])
def reset():
    ec2 = boto3.resource("ec2")
    lambda_client = boto3.client("lambda")

    for instance_id in warmup_state["instances"]:
        instance = ec2.Instance(instance_id)

        # Input Parameters for the Lambda function
        input_params = {
            "instance_id": instance.id,
        }

        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName="reset",  # replace with your actual Lambda function name
            InvocationType="Event",
            Payload=json.dumps(input_params),
        )
    return jsonify({"result": "ok"})


@app.route("/terminate", methods=["GET"])
def terminate():

    def terminate_resources():
        s = warmup_state["service"]

        if s != None:
            if s.lower() == "ec2":
                helper.terminate_ec2_instances()
                helper.terminate_dynamodb_tables(table_name)

        warmup_state["warm"] = False
        warmup_state["service"] = None
        warmup_state["terminated"] = True

    # Start the termination process in a new thread
    thread = threading.Thread(target=terminate_resources)
    thread.start()

    return jsonify({"result": "ok"})


@app.route("/scaled_terminated", methods=["GET"])
def scaled_terminate():
    ec2 = boto3.resource("ec2")
    if len(warmup_state["instances"]) == 0:
        return jsonify({"terminated": warmup_state["terminated"]})
    for instances in warmup_state["instances"]:
        instance = ec2.Instance(instances)
        if instance.state["Name"] != "terminated":
            warmup_state["terminated"] = False
            break
    return jsonify({"terminated": warmup_state["terminated"]})


if __name__ == "__main__":
    app.run(debug=True, port=8080)
