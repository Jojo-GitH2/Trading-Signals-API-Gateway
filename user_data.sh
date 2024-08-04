#!/bin/bash
sudo yum update -y
sudo yum install -y python3 python3-pip && pip3 install --ignore-installed yfinance
cd /home/ec2-user
echo '
import yfinance as yf
from datetime import date, timedelta
import sys
import math
import random
import json
import time


def risk_analysis(h, d, t, p):
    start_time = time.time()
    # Get stock data from Yahoo Finance
    today = date.today()
    timePast = today - timedelta(days=h)
    data = yf.download("NVDA", start=timePast, end=today)
    results = {"var95": [], "var99": [], "profit_loss": []}
    # Convert the data to a list of lists
    data_list = [list(row) for row in data.values]
    daily_returns = [
        (data_list[i][3] - data_list[i - 1][3]) / data_list[i - 1][3] for i in range(1, len(data_list))
    ]

    # Perform the risk analysis for each signal
    for i in range(2, len(data_list)):
        body = 0.01
        # Three Soldiers
        if (
            (data_list[i][3] - data_list[i][0]) >= body
            and data_list[i][3] > data_list[i - 1][3]
            and (data_list[i - 1][3] - data_list[i - 1][0]) >= body
            and data_list[i - 1][3] > data_list[i - 2][3]
            and (data_list[i - 2][3] - data_list[i - 2][0]) >= body
        ):
            signal = 1
        # Three Crows
        elif (
            (data_list[i][0] - data_list[i][3]) >= body
            and data_list[i][3] < data_list[i - 1][3]
            and (data_list[i - 1][0] - data_list[i - 1][3]) >= body
            and data_list[i - 1][3] < data_list[i - 2][3]
            and (data_list[i - 2][0] - data_list[i - 2][3]) >= body
        ):
            signal = -1
        else:
            signal = 0

        if (signal == 1 and t == "buy") or (signal == -1 and t == "sell"):
            # Generate d simulated returns
            pct_change = [daily_returns[i - h : i]][0]

            mean = sum(pct_change) / h
            std = math.sqrt(sum([(x - mean) ** 2 for x in pct_change]) / h)

            simulated = [random.gauss(mean, std) for _ in range(d)]

            # Calculate the 95% and 99% VaR
            simulated.sort(reverse=True)
            var95 = simulated[int(len(simulated) * 0.95)]
            var99 = simulated[int(len(simulated) * 0.99)]
            results["var95"].append(var95)
            results["var99"].append(var99)

            # Calculate the profit or loss
            if i + p < len(data_list):
                if t == "buy":
                    profit_loss = data_list[i + p][3] - data_list[i][3]
                elif t == "sell":
                    profit_loss = data_list[i][3] - data_list[i + p][3]
                results["profit_loss"].append(profit_loss)
    results["execution_time"] = time.time() - start_time
    with open("/home/ec2-user/data.json", "w") as f:
        json.dump(results, f)


if __name__ == "__main__":
    h = int(sys.argv[1])
    d = int(sys.argv[2])
    t = sys.argv[3]
    p = int(sys.argv[4])
    risk_analysis(h, d, t, p)' > /home/ec2-user/risk_analysis.py
sudo chmod 755 /home/ec2-user/risk_analysis.py
sudo chown ec2-user:ec2-user /home/ec2-user/risk_analysis.py
nohup python3 -m http.server 5000 &