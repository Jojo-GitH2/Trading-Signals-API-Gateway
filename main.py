from flask import Flask, request, jsonify, render_template
# import boto3
# import json
# import helper
import os
import time
import numpy as np
import requests
import datetime
import threading

# import risk_analysis

app = Flask(__name__)

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# # Run one of this on the command line before running the code below:
# # To create a secret with the AWS credentials in the Google Secret Manager
# # gcloud secrets create aws-credentials  --data-file=C:\Users\Lawal\.aws\credentials --project=trading-signals-418515

# # To Update the secret with the AWS credentials in the Google Secret Manager
# # gcloud secrets versions add aws-credentials --data-file=C:\Users\Lawal\.aws\credentials --project=trading-signals-418515

# if os.getenv("GAE_ENV", "").startswith("standard"):
#     # Authenticate with AWS
#     aws_credentials = helper.get_secret(
#         project_id="trading-signals-418515", secret_id="aws-credentials"
#     )

#     try:
#         lines = aws_credentials.split("\n")
#         if len(lines) < 4:
#             raise ValueError("Invalid AWS credentials format")

#         aws_access_key_id = lines[1].split("=")[1].strip()
#         aws_secret_access_key = lines[2].split("=")[1].strip()
#         aws_session_token = lines[3].split("=")[1].strip()

#     except IndexError:
#         print("Error: AWS credentials file is not in the expected format.")
#     except ValueError as ve:
#         print(f"Error: {ve}")

#     # Configure boto3 with your AWS credentials
#     boto3.setup_default_session(
#         aws_access_key_id=aws_access_key_id,
#         aws_secret_access_key=aws_secret_access_key,
#         aws_session_token=aws_session_token,
#     )

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

        warmup_api = (
            "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/warmup"
        )
        headers = {"Content-Type": "application/json"}
        start_time = time.time()
        response = requests.post(
            warmup_api,
            json=data,
            headers=headers,
        )
        end_time = time.time()
        warmup_state["warmup_time"] = end_time - start_time

        instance_ids = response.json()["instance_ids"]

        if instance_ids != list():
            warmup_state["terminated"] = False
            warmup_state["instances"] = instance_ids

    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify({"result": "ok"})


@app.route("/scaled_ready", methods=["GET"])
def scaled_ready():
    if len(warmup_state["instances"]) == 0:
        return jsonify({"warm": False})

    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/scaled_ready"

    headers = {"Content-Type": "application/json"}

    instances = warmup_state["instances"]

    response = requests.post(api, json={"instances": instances}, headers=headers)

    warmup_state["warm"] = response.json()["warm"]

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
    instances = warmup_state["instances"]
    if len(instances) == 0:
        return jsonify({})
    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/get_endpoints"

    headers = {"Content-Type": "application/json"}

    instances = warmup_state["instances"]

    response = requests.post(api, json={"instances": instances}, headers=headers)

    return jsonify(response.json())


@app.route("/analyse", methods=["POST"])
def analyse():
    def put_item(api, data, headers):
        response = requests.post(api, json=data, headers=headers)
    data = request.get_json()
    data["instances"] = warmup_state["instances"]

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
        analyse_api = (
            "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/analyse"
        )
        headers = {"Content-Type": "application/json"}
        response = requests.post(analyse_api, json=data, headers=headers)

        if response.status_code == 200:
            endpoints = get_endpoints().get_json()
            execution_times = [
                requests.get(url).json()["execution_time"] for url in endpoints.values()
            ]
            execution_time = sum(execution_times) / len(execution_times)
            total_time = execution_time * len(execution_times)

            averages = get_avg_vars9599().get_json()

        put_item_api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/analyse/put_item"
        items = {
            "timestamp": datetime.datetime.now().isoformat(),
            "s": warmup_state["service"],
            "r": str(warmup_state["scale"]),
            "h": str(h),
            "d": d,
            "t": t,
            "p": str(p),
            "av95": str(averages["var95"]),
            "av99": str(averages["var99"]),
            "profit_loss": str(get_tot_profit_loss().get_json()["profit_loss"]),
            "time": str(f"{execution_time:.5f} seconds"),
            "cost": str(f"${total_time * 0.0116:.5f}"),
        }
        headers = {"Content-Type": "application/json"}

        thread = threading.Thread(target=put_item, args=(put_item_api, items, headers))
        thread.start()

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
    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/analyse/get_time_cost"
    response = requests.get(api)
    return jsonify(response.json())


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
    api = (
        "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/analyse/get_audit"
    )

    headers = {"Content-Type": "application/json"}
    response = requests.get(api, headers=headers)
    return jsonify(response.json()["Items"])


@app.route("/reset", methods=["GET"])
def reset():
    instances = warmup_state["instances"]
    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/analyse/reset"
    headers = {"Content-Type": "application/json"}

    response = requests.post(api, json=instances, headers=headers)

    return jsonify({"result": "ok"})


@app.route("/terminate", methods=["GET"])
def terminate():

    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/terminate"

    headers = {"Content-Type": "application/json", "InvocationType": "Event"}

    response = requests.get(api, headers=headers)

    warmup_state["warm"] = False
    warmup_state["service"] = None
    warmup_state["terminated"] = True


    return jsonify({"result": "ok"})


@app.route("/scaled_terminated", methods=["GET"])
def scaled_terminate():

    instances = warmup_state["instances"]
    api = "https://uc011ejq61.execute-api.us-east-1.amazonaws.com/prod/terminate/scaled_terminated"
    headers = {"Content-Type": "application/json"}
    response = requests.post(api, json=instances, headers=headers)

    warmup_state["terminated"] = response.json()["terminated"]
    
    return jsonify({"terminated": warmup_state["terminated"]})


if __name__ == "__main__":
    app.run(debug=True, port=8080)
