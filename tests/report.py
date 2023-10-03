import os
import json
from time import sleep, time
from datetime import datetime

import boto3
import requests

TDS_URL = os.environ.get("TDS_URL", "http://data-service:8000")
PYCIEMSS_URL = os.environ.get("PYCIEMSS_URL", "http://pyciemss-api:8000")
SCIML_URL = os.environ.get("SCIML_URL", "http://sciml-service:8080")
BUCKET = os.environ.get("BUCKET", None)


def eval_integration(service_name, endpoint, request):
    start_time = time()
    is_success = False
    base_url = PYCIEMSS_URL if service_name == "pyciemss" else SCIML_URL
    kickoff_request = requests.post(f"{base_url}/{endpoint}", json=request, 
        headers= {
            "Content-Type": "application/json"
        }    
    )
    if kickoff_request.status_code < 300:
        sim_id = kickoff_request.json()["simulation_id"]
        get_status = lambda: requests.get(f"{base_url}/status/{sim_id}").json()["status"]
        while get_status() in ["queued", "running"]:
            sleep(1)
        if get_status() == "complete":
            is_success = True
    return {
        "Integration Status": is_success,
        "Execution Time": time() - start_time
    }


def gen_report():
    report = {
        "scenarios": {
            "pyciemss": {},
            "sciml": {}
        }, 
        "services": {
            "TDS": {
                "version": "UNAVAILABLE"
            },
            "PyCIEMSS Service": {
                "version": "UNAVAILABLE"
            },
            "SciML Service": {
                "version": "UNAVAILABLE"
            },
        }
    }

    
    report["scenarios"] = {name: {} for name in os.listdir("scenarios")}
    for scenario in report["scenarios"]:
        scenario_spec = {}
        for backend in ["pyciemss", "sciml"]:
            path = f"scenarios/{scenario}/{backend}"
            if os.path.exists(path):
                scenario_spec[backend] = os.listdir(f"scenarios/{scenario}/{backend}")
        for service_name, tests in scenario_spec.items():
            for test_file in tests:
                test = test_file.split(".")[0]
                name = f"{service_name}-{test}"
                file = open(f"scenarios/{scenario}/{service_name}/{test_file}", "rb") 
                print(f"Trying `/{endpoint}` ({service_name}, {scenario})")
                report["scenarios"][scenario][name] = eval_integration(service_name, test, json.load(file))
                print(f"Completed `/{endpoint}` ({service_name}, {scenario})")
    return report


def publish_report(report, upload):
    print("Publishing report")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}.json"
    fullpath = os.path.join("reports", filename)
    os.makedirs("reports", exist_ok=True)
    with open(fullpath, "w") as file:
        json.dump(report, file, indent=2)

    if upload:
        print("Uploading report")
        s3 = boto3.client("s3")
        full_handle = os.path.join("ta3", filename)
        s3.upload_file(fullpath, BUCKET, full_handle)


def report(upload=True):
    publish_report(gen_report(), upload)


if __name__ == "__main__":
    report(BUCKET is not None)