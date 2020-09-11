from nornir import InitNornir
from nornir.plugins.tasks.networking import napalm_configure
from nornir.plugins.functions.text import print_result
from nornir.core.filter import F

from tqdm import tqdm
import sys,logging



def process_tasks(task):
    if task.failed:
        print_result(task)
        print("Exiting script before we break anything else!")
        sys.exit(1)
    else:
        print(f"Task {task.name} completed successfully!")

def deploy_configuration(task,progress_bar,conf_text):
    deploy = task.run(task=napalm_configure,
             name="Deploy Configuration",
             configuration=conf_text,
             replace=False,
         severity_level=logging.INFO)
    tqdm.write(f"{task.host}: Deploy Configuration complete")
    progress_bar.update()

def _deploy_config(conf_text):
    nr = InitNornir(config_file="nornir_config.yaml")
    all_devices = nr.filter(F(groups__contains="peering"))
    with tqdm(total=len(all_devices.inventory.hosts), desc="Deploy Configuration",) as progress_bar:
        deploy_configuration_task = all_devices.run(task=deploy_configuration,progress_bar=progress_bar,conf_text=conf_text)
    process_tasks(deploy_configuration_task)