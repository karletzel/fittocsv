import functions_framework

@functions_framework.cloud_event
def process_fit_file(cloud_event):
    print("Function is super live! Waiting for FIT file...")
