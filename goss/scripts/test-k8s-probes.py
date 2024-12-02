import json
import subprocess

import requests


def get_pod_ips(namespace):
    command = f"kubectl get pods -n {namespace} -o jsonpath='{{.items[*].status.podIP}}'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        return result.stdout.split()
    print("Failed to retrieve pod IPs.")
    return []

def check_health(ip):
    try:
        response = requests.get(f"http://{ip}:38812/v1/health")
        response_data = json.loads(response.text)
        return response_data.get('result', {}).get('healthy')
    except requests.RequestException:
        return False

def main():
    """Query each charm container's /v1/health API."""
    namespace = "cos-model"
    pod_ips = get_pod_ips(namespace)
    for ip in pod_ips:
        if not check_health(ip):
            print(f"Curl failed for {ip}")

if __name__ == "__main__":
    main()
