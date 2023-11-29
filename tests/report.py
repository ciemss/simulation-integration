import os
import json
import logging
from time import sleep, time
from datetime import datetime
from collections import defaultdict
from urllib.parse import urljoin

import boto3
import requests

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

TDS_URL = os.environ.get("TDS_URL", "http://data-service:8000")
PYCIEMSS_URL = os.environ.get("PYCIEMSS_URL", "http://pyciemss-api:8000")
SCIML_URL = os.environ.get("SCIML_URL", "http://sciml-service:8080")
BUCKET = os.environ.get("BUCKET", None)
UPLOAD = os.environ.get("UPLOAD", "FALSE").lower() == "true"


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
    def get_version(base_url):
        response = requests.get(urljoin(base_url, "health"))        
        if response.status_code < 300:
            return response.json()["git_sha"]
        else:
            return f"UNAVAILABLE: {response.status_code}"

    report = {
        "scenarios": {
            "pyciemss": defaultdict(dict),
            "sciml": defaultdict(dict)
        },
        "services": {
            "TDS": {
                "version": get_version(TDS_URL)
            },
            "PyCIEMSS Service": {
                "version": get_version(PYCIEMSS_URL)
            },
            "SciML Service": {
                "version": get_version(SCIML_URL)
            },
        }
    }


    scenarios = {name: {} for name in os.listdir("scenarios")}
    for scenario in scenarios:
        scenario_spec = {}
        for backend in ["pyciemss", "sciml"]:
            path = f"scenarios/{scenario}/{backend}"
            if os.path.exists(path):
                scenario_spec[backend] = [f for f in os.listdir(f"scenarios/{scenario}/{backend}")
                                          if f.endswith(".json")] # only grab json files (ignore hidden notebooks)t
        for service_name, tests in scenario_spec.items():
            for test_file in tests:
                test = test_file.split(".")[0]
                file = open(f"scenarios/{scenario}/{service_name}/{test_file}", "rb")
                logging.info(f"Trying `/{test}` ({service_name}, {scenario})")
                report["scenarios"][service_name][scenario][test] = eval_integration(service_name, test, json.load(file))
                logging.info(f"Completed `/{test}` ({service_name}, {scenario})")
    return report


def publish_report(report, upload):
    logging.info("Publishing report")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}.json"
    fullpath = os.path.join("/outputs/ta3", filename)
    os.makedirs("/outputs/ta3", exist_ok=True)
    with open(fullpath, "w") as file:
        json.dump(report, file, indent=2)

    if upload and BUCKET is not None:
        logging.info(f"Uploading report to '{BUCKET}'")
        s3 = boto3.client("s3")
        full_handle = os.path.join("ta3", filename)
        s3.upload_file(fullpath, BUCKET, full_handle)

    elif upload and BUCKET is None:
        logging.error("NO BUCKET WAS PROVIDED. CANNOT UPLOAD")

    if not upload or BUCKET is None:
        logging.info(f"{fullpath}:")
        logging.info(open(fullpath, "r").read())


def report(upload=True):
    publish_report(gen_report(), upload)


if __name__ == "__main__":
    report(UPLOAD)
