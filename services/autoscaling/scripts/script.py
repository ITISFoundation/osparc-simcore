#
# Moved by pcrespov from allexandre/osparc-dask-auto-scaling/-/blob/master/script.py
#

import math
import re
import time
from datetime import datetime, timedelta

import boto3
import dask_gateway
import docker
from dask.distributed import Client, Scheduler
from environs import Env

# Init :Check that schduler is working, if not use the notebook to start it - remove old node in the swarm and in aws
# TODO add python -m pip install dask distributed --upgrade to requirements
# TODO Case when ressources asked are not meet by any sidecar resource resctrictions all tasks mis dictionnaire  cluster scheduler worker_Info
# Sylvain 3.8.10
env = Env()
env.read_env()

local_file_directory = "data"
Scheduler.pickle = True
docker_client = docker.from_env()

list_created_clusters = []


aws_EC2 = [
    # { "name": "t2.nano", "CPUs" : 1, "RAM" : 0.5},
    # { "name": "t2.micro", "CPUs" : 1, "RAM" : 1},
    # { "name": "t2.small", "CPUs" : 1, "RAM" : 2},
    # { "name": "t2.medium", "CPUs" : 2, "RAM" : 4},
    # { "name": "t2.large", "CPUs" : 2, "RAM" : 8},
    {"name": "t2.xlarge", "CPUs": 4, "RAM": 16},
    {"name": "t2.2xlarge", "CPUs": 8, "RAM": 32},
    {"name": "r5n.4xlarge", "CPUs": 16, "RAM": 128},
    {"name": "r5n.8xlarge", "CPUs": 32, "RAM": 256}
    #  { "name": "r5n.12xlarge", "CPUs" : 48, "RAM" : 384},
    # { "name": "r5n.16xlarge", "CPUs" : 64, "RAM" : 512},
    # { "name": "r5n.24xlarge", "CPUs" : 96, "RAM" : 768}
]

# THanks to https://gist.github.com/shawnbutts/3906915
def bytesto(bytes, to, bsize=1024):
    """convert bytes to megabytes, etc.
    sample code:
        print('mb= ' + str(bytesto(314575262000000, 'm')))
    sample output:
        mb= 300002347.946
    """
    a = {"k": 1, "m": 2, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    for i in range(a[to]):
        r = r / bsize
    return r


# Inteveral between checks in s
check_time = int(env.str("INTERVAL_CHECK"))


def get_number_of_tasks(dask_scheduler=None):
    return f"{dask_scheduler.tasks}"


def get_workers_info(dask_scheduler=None):
    return f"{dask_scheduler.workers}"


def check_node_resources():
    nodes = docker_client.nodes.list()
    # We compile RAM and CPU capabilities of each node who have the label sidecar
    # TODO take in account personalized workers
    # Total resources of the cluster
    nodes_sidecar_data = []
    for node in nodes:
        for label in node.attrs["Spec"]["Labels"]:
            if label == "sidecar":
                nodes_sidecar_data.append(
                    {
                        "ID": node.attrs["ID"],
                        "RAM": bytesto(
                            node.attrs["Description"]["Resources"]["MemoryBytes"],
                            "g",
                            bsize=1024,
                        ),
                        "CPU": int(node.attrs["Description"]["Resources"]["NanoCPUs"])
                        / 1000000000,
                    }
                )

    total_nodes_cpus = 0
    total_nodes_ram = 0
    nodes_ids = []
    for node in nodes_sidecar_data:
        total_nodes_cpus = total_nodes_cpus + node["CPU"]
        total_nodes_ram = total_nodes_ram + node["RAM"]
        nodes_ids.append(node["ID"])

    return {
        "total_cpus": total_nodes_cpus,
        "total_ram": total_nodes_ram,
        "nodes_ids": nodes_ids,
    }


# TODO discuss with the team consideration between limits and reservations on dy services
def check_tasks_resources(nodes_ids):
    total_tasks_cpus = 0
    total_tasks_ram = 0
    tasks_ressources = []
    total_pending_tasks_cpus = 0
    total_pending_tasks_ram = 0
    tasks_pending_ressources = []
    serv = docker_client.services.list()
    count_tasks_pending = 0
    for service in serv:
        tasks = service.tasks()
        for task in tasks:
            if task["Status"]["State"] == "running" and task["NodeID"] in nodes_ids:
                if "Resources" in task["Spec"] and task["Spec"]["Resources"] != {}:
                    ram = 0
                    cpu = 0
                    if "Reservations" in task["Spec"]["Resources"]:
                        if "MemoryBytes" in task["Spec"]["Resources"]["Reservations"]:
                            ram = bytesto(
                                task["Spec"]["Resources"]["Reservations"][
                                    "MemoryBytes"
                                ],
                                "g",
                                bsize=1024,
                            )
                        if "NanoCPUs" in task["Spec"]["Resources"]["Reservations"]:
                            cpu = (
                                int(
                                    task["Spec"]["Resources"]["Reservations"][
                                        "NanoCPUs"
                                    ]
                                )
                                / 1000000000
                            )
                    tasks_ressources.append({"ID": task["ID"], "RAM": ram, "CPU": cpu})

            elif (
                task["Status"]["State"] == "pending"
                and task["Status"]["Message"] == "pending task scheduling"
                and "insufficient resources on" in task["Status"]["Err"]
            ):
                count_tasks_pending = count_tasks_pending + 1
                if "Resources" in task["Spec"] and task["Spec"]["Resources"] != {}:
                    ram = 0
                    cpu = 0
                    if "Reservations" in task["Spec"]["Resources"]:
                        if "MemoryBytes" in task["Spec"]["Resources"]["Reservations"]:
                            ram = bytesto(
                                task["Spec"]["Resources"]["Reservations"][
                                    "MemoryBytes"
                                ],
                                "g",
                                bsize=1024,
                            )
                        if "NanoCPUs" in task["Spec"]["Resources"]["Reservations"]:
                            cpu = (
                                int(
                                    task["Spec"]["Resources"]["Reservations"][
                                        "NanoCPUs"
                                    ]
                                )
                                / 1000000000
                            )
                    tasks_pending_ressources.append(
                        {"ID": task["ID"], "RAM": ram, "CPU": cpu}
                    )

    total_tasks_cpus = 0
    total_tasks_ram = 0
    for task in tasks_ressources:
        total_tasks_cpus = total_tasks_cpus + task["CPU"]
        total_tasks_ram = total_tasks_ram + task["RAM"]

    for task in tasks_pending_ressources:
        total_pending_tasks_cpus = total_pending_tasks_cpus + task["CPU"]
        total_pending_tasks_ram = total_pending_tasks_ram + task["RAM"]
    return {
        "total_cpus_running_tasks": total_tasks_cpus,
        "total_ram_running_tasks": total_tasks_ram,
        "total_cpus_pending_tasks": total_pending_tasks_cpus,
        "total_ram_pending_tasks": total_pending_tasks_ram,
        "count_tasks_pending": count_tasks_pending,
    }


# Check if the swarm need to scale up
# TODO currently the script has to be executed directly on the manager. Implenting a version that connect with ssh and handle the case when one manager is down to be able to have redundancy
def check_dynamic():
    user_data = (
        """#!/bin/bash
    cd /home/ubuntu
    hostname=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "hostname" 2>&1)
    token=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker swarm join-token -q worker")
    host=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker swarm join-token worker" 2>&1)
    docker swarm join --token ${token} ${host##* }
    label=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker node ls | grep $(hostname)")
    label="$(cut -d' ' -f1 <<<"$label")"
    ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker node update --label-add sidecar=true $label"
    ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker node update --label-add standardworker=true $label"
    """
    )
    # docker_client.containers.run("ubuntu:latest", "echo hello world")
    serv = docker_client.services.list()
    # We need the data of each task and the data of each node to know if we need to scale up or not
    # Test if some tasks are in a pending mode because of a lack of resources
    need_resources = False
    for service in serv:
        tasks = service.tasks()
        for task in tasks:
            if (
                task["Status"]["State"] == "pending"
                and task["Status"]["Message"] == "pending task scheduling"
                and "insufficient resources on" in task["Status"]["Err"]
            ):
                need_resources = True
                break

    # We compile RAM and CPU capabilities of each node who have the label sidecar
    # TODO take in account personalized workers
    # Total resources of the cluster
    if need_resources:
        total_nodes = check_node_resources()
        total_tasks = check_tasks_resources(total_nodes["nodes_ids"])
        available_cpus = (
            total_nodes["total_cpus"] - total_tasks["total_cpus_running_tasks"]
        )
        available_ram = (
            total_nodes["total_ram"] - total_tasks["total_ram_running_tasks"]
        )
        # print("avail cpuz" + str(available_cpus) + " avail ram" + str(available_ram))
        needed_cpus = (
            available_cpus - total_tasks["total_cpus_pending_tasks"]
        ) * -1 + 2  # Cpus used for other tasks
        needed_ram = (
            available_ram - total_tasks["total_ram_pending_tasks"]
        ) * -1 + 4  # Ram used for other stasks
        # print("taskcpus_needed : " + str(total_tasks["total_cpus_pending_tasks"]) + " staskRAMneeded : " + str(total_tasks["total_ram_pending_tasks"]))
        print(
            "The Swarm currently has "
            + str(total_tasks["count_tasks_pending"])
            + " task(s) in pending mode"
        )
        # print("Theses task require a total of " + str(needed_cpus) + " cpus and " + str(needed_ram) + " GB of RAM in order to be executed.")
        print(
            "Theses task(s) require a total of "
            + str(math.ceil(total_tasks["total_cpus_pending_tasks"]))
            + " cpus and "
            + str(math.ceil(total_tasks["total_ram_pending_tasks"]))
            + " GB of RAM in order to be executed."
        )
        for instance in aws_EC2:
            # if instance["CPUs"] >= needed_cpus and instance["RAM"] >= needed_ram:
            if instance["CPUs"] >= math.ceil(
                total_tasks["total_cpus_pending_tasks"]
            ) and instance["RAM"] >= math.ceil(total_tasks["total_ram_pending_tasks"]):
                now = datetime.now() + timedelta(hours=2)
                dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
                print(
                    "A new EC2 instance has been selected to add more resources to the cluster. Name : "
                    + instance["name"]
                    + " Cpus : "
                    + str(instance["CPUs"])
                    + " RAM : "
                    + str(instance["RAM"])
                    + "GB"
                )
                start_instance_aws(
                    "ami-097895f2d7d86f07e",
                    instance["name"],
                    "Autoscaling node " + dt_string,
                    "dynamic",
                    user_data,
                )
                break
    else:
        print("No pending task(s) on the swarm detected.")

        # TODO Better algorythm


# TODO VPn handling is bad
# If no cluster I create one
# Test how it works without cluster
# To start the script for the first time, create the cluster with a jupyter notebook
def check_computationnal():
    # When we launch a new task, we check if the desired capacity doesn't exceed the total cluster capacity or the most powerful worker capacity
    g = dask_gateway.Gateway(
        address=env.str("DASK_GATEWAY_ADDRESS"),
        auth=dask_gateway.BasicAuth(
            env.str("DASK_GATEWAY_LOGIN"), env.str("DASK_GATEWAY_PWD")
        ),
    )

    # At first, we need to create a cluster if there is none
    if g.list_clusters() == []:
        print("Currently 0 cluster in the gateway. We create a new one")
        list_created_clusters.append(g.new_cluster())

    cluster = g.connect(g.list_clusters()[0].name)
    # cluster.adapt(minimum=1, maximum=100)
    scheduler_infos = cluster.scheduler_info
    client = cluster.get_client()

    max_worker_CPUs = 0
    max_worker_RAM = 0
    total_worker_CPUs = 0
    total_worker_RAM = 0
    print(scheduler_infos)
    # cluster.adapt(minimum=1, maximum=15)
    # TODO: case where a task want something which has enough RAM on one sidecar and enough CPU in another one but no sidecar has both ressources
    for worker in scheduler_infos["workers"].values():
        total_worker_CPUs = total_worker_CPUs + int(worker["resources"]["CPU"])
        total_worker_RAM = total_worker_RAM + int(worker["resources"]["RAM"])
        if int(worker["resources"]["CPU"]) > max_worker_CPUs:
            max_worker_CPUs = int(worker["resources"]["CPU"])
        if int(worker["resources"]["RAM"]) > max_worker_RAM:
            max_worker_RAM = int(worker["resources"]["RAM"])

    max_worker_RAM = bytesto(max_worker_RAM, "g", bsize=1024)
    total_worker_RAM = bytesto(total_worker_RAM, "g", bsize=1024)
    # cl= Client("gateway://test.test.osparc.io:8000/993bb0c4a51f4d44bd41393679a56c8d")

    # print("Total workers CPUs : " +  str(total_worker_CPUs))
    # print("Total workers RAM : " +  str(round(total_worker_RAM, 1)) + "G")
    # print("Max worker CPUs : " +  str(max_worker_CPUs))
    # print("Total workers RAM : " +  str(round(max_worker_RAM, 1)) + "G")
    # s = Scheduler()
    # print(cluster.scheduler_comm)
    cl = Client(cluster, security=cluster.security)
    # print(g.proxy_address)
    # print(cl.dashboard_link)

    # s = Scheduler(host="test.test.osparc.io/993bb0c4a51f4d44bd41393679a56c8d", port=8000, protocol="gateway", interface=)
    # s.workers_list
    # print(s.status)
    tasks_infos = cl.run_on_scheduler(get_number_of_tasks)
    # print(tasks_infos)
    workers_infos = cl.run_on_scheduler(get_workers_info)
    # workers_infos_dic_formatted = workers_infos.replace('SortedDict(', '')[:-1]
    # print(workers_infos_dic_formatted)
    # res = json.loads(workers_infos_dic_formatted)
    result = re.search("processing: (.*)>", workers_infos)
    if result is None:
        total_tasks = 0
    else:
        total_tasks = int(result.group(1))
    print("Current number of tasks managed by the scheduler : " + str(total_tasks))

    # print(workers_infos.get("processing"))
    # print(workers_infos)
    # res = json.loads(workers_infos_dic_formatted)
    print("Current number of workers : " + str(len(client.scheduler_info()["workers"])))
    task_handled = 0
    # IN this scenario, we look at the first worker only. In the future we need to look at all the workers
    if len(client.scheduler_info()["workers"]) > 0:
        workers_keys = list(client.scheduler_info()["workers"].keys())[0]
        print(
            "Number of tasks currently executed by the workers : "
            + str(
                client.scheduler_info()["workers"][workers_keys]["metrics"]["executing"]
            )
        )
        task_handled = client.scheduler_info()["workers"][workers_keys]["metrics"][
            "executing"
        ]
    if task_handled < total_tasks:
        print(
            "The clusted can't handle the current load... Auto-scaling to add a new host"
        )
        scale_up(2, 4)
    else:
        print("Computational services :Current cluster state OK, pausing for 30s.....")

    # print(client.status)
    # Worker.ge

    # if task[CPU] > max_worker_CPUs or task[RAM] > max_worker_RAM:

    # Sample task
    # future = client.submit(add, 132,423, resources={"CPU":10}, pure=False)
    # future.result()


# THanks to https://gist.github.com/shawnbutts/3906915
def bytesto(bytes, to, bsize=1024):
    """convert bytes to megabytes, etc.
    sample code:
        print('mb= ' + str(bytesto(314575262000000, 'm')))
    sample output:
        mb= 300002347.946
    """
    a = {"k": 1, "m": 2, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    for i in range(a[to]):
        r = r / bsize
    return r


def add(x, y):
    time.sleep(120)
    return x + y


def scale_up(CPUs, RAM):
    print("Processing the new instance on AWS..")

    # Has to be disccused
    for host in aws_EC2:
        if host["CPUs"] >= CPUs and host["RAM"] >= RAM:
            new_host = host

    # Do we pass our scaling limits ?
    # if total_worker_CPUs + host["CPUs"] >= int(env.str("MAX_CPUs_CLUSTER")) or total_worker_RAM + host["RAM"] >= int(env.str("MAX_RAM_CLUSTER")):
    #    print("Error : We would pass the defined cluster limits in term of RAM/CPUs. We can't scale up")
    # else:
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    user_data = (
        """#!/bin/bash
    cd /home/ubuntu
    hostname=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "hostname" 2>&1)
    token=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker swarm join-token -q worker")
    host=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker swarm join-token worker" 2>&1)
    docker swarm join --token ${token} ${host##* }
    label=$(ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker node ls | grep $(hostname)")
    label="$(cut -d' ' -f1 <<<"$label")"
    ssh -i """
        + env.str("AWS_KEY_NAME")
        + """.pem -oStrictHostKeyChecking=no ubuntu@"""
        + env.str("AWS_DNS")
        + """ "docker node update --label-add sidecar=true $label"
    reboot_hour=$(last reboot | head -1 | awk '{print $8}')
    reboot_mn="${reboot_hour: -2}"
    if [ $reboot_mn -gt 4 ]
    then
            cron_mn=$((${reboot_mn} - 5))
    else
            cron_mn=55
    fi
    echo ${cron_mn}
    cron_mn+=" * * * * /home/ubuntu/cron_terminate.bash"
    cron_mn="*/10 * * * * /home/ubuntu/cron_terminate.bash"
    echo "${cron_mn}"
    (crontab -u ubuntu -l; echo "$cron_mn" ) | crontab -u ubuntu -
    """
    )
    start_instance_aws(
        "ami-0699f9dc425967eba",
        "t2.2xlarge",
        "Autoscaling node " + dt_string,
        "computational",
        user_data,
    )


def start_instance_aws(ami_id, instance_type, tag, type, user_data):
    ec2Client = boto3.client(
        "ec2",
        aws_access_key_id=env.str("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=env.str("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
    )
    ec2Resource = boto3.resource("ec2", region_name="us-east-1")
    ec2 = boto3.resource("ec2", region_name="us-east-1")
    # TODO check bug on the auto-terminate ?
    # Create the instance
    instanceDict = ec2.create_instances(
        ImageId=ami_id,
        KeyName=env.str("AWS_KEY_NAME"),
        InstanceType=instance_type,
        SecurityGroupIds=[env.str("SECURITY_GROUP_IDS")],  # Have to be parametrized
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior="terminate",
        SubnetId=env.str("SUBNET_ID"),  # Have to be parametrized
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": tag}]}
        ],
        UserData=user_data,
    )
    instanceDict = instanceDict[0]
    print(
        "New instance launched for "
        + type
        + " services. Estimated time to launch and join the cluster : 2mns"
    )
    print("Pausing for 10mns before next check")
    time.sleep(600)
    # print("Instance state: %s" % instanceDict.state)
    # print("Public dns: %s" % instanceDict.public_dns_name)
    # print("Instance id: %s" % instanceDict.id)


if __name__ == "__main__":
    while True:
        # check_computationnal()
        check_dynamic()
        time.sleep(check_time)
