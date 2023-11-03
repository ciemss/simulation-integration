from glob import glob
import json
import os

import requests

TDS_URL = os.environ.get("TDS_URL", "http://data-service:8000")

model_configs = glob("./data/models/*.json")
for config_path in model_configs:
    print(config_path)
    config = json.load(open(config_path, 'rb'))
    if "configuration" not in config:
        print(config_path)
    else:
        model = config["configuration"]
    model_response = requests.post(TDS_URL + "/models", json=model, headers={
        "Content-Type": "application/json"
    })
    if model_response.status_code >= 300:
        raise Exception(f"Failed to POST model ({model_response.status_code}): {config['id']}")
    config["model_id"] = model_response.json()["id"]
    config_response = requests.post(TDS_URL + "/model_configurations", json=config,
        headers= {
            "Content-Type": "application/json"
        }    
    )

    
    if config_response.status_code >= 300:
        raise Exception(f"Failed to POST config ({config_response.status_code}): {config['id']}")

datasets = glob("./data/datasets/*.csv")
for filepath in datasets:
    filename = filepath.split("/")[-1]
    dataset_name = filename.split(".")[0]
    dataset = {
        "id": dataset_name,
        "name": dataset_name,
        "file_names": [
            filename
        ]
    }
    dataset_response = requests.post(TDS_URL + "/datasets", json=dataset,
        headers= {
            "Content-Type": "application/json"
        }    
    )
    if dataset_response.status_code >= 300:
        raise Exception(f"Failed to POSt dataset ({dataset_response.status_code}): {dataset['name']}")
    url_response = requests.get(TDS_URL + f"/datasets/{dataset_name}/upload-url", params={"filename": filename})
    upload_url = url_response.json()["url"]
    with open(filepath, "rb") as file:
        requests.put(upload_url, file)
        
