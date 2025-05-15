import requests
import json
import time

def submit_job(job_data):
    """提交新作业到服务器"""
    response = requests.post(
        "http://localhost:8500/jobs",
        json=job_data,
        headers={"Content-Type": "application/json"}
    )
    return response.json()

def update_job(job_id, job_data):
    """更新已有作业"""
    response = requests.put(
        f"http://localhost:8500/jobs/{job_id}",
        json=job_data,
        headers={"Content-Type": "application/json"}
    )
    return response.json()

def stop_job(job_id):
    """停止作业"""
    response = requests.delete(
        f"http://localhost:8500/jobs/{job_id}",
        headers={"Content-Type": "application/json"}
    )
    return response.json()

def main():
    # 测试用例0：提交新作业  "command": "python my_script.py"
    job0 = {
        "task_groups": [
            {
                "name": "my_scripts",
                "tasks": [
                    {
                        "name": "my_script",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "command": "python my_script.py"
                        }
                    }
                ],
                "constraints": [ 
                    {
                        "attribute": "node_id",
                        "operator": "=",
                        "value": "1234567890"
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }

    print("\n测试0：提交新作业")
    result0 = submit_job(job0)
    print(f"结果：{json.dumps(result0, indent=2, ensure_ascii=False)}")

    time.sleep(10)
    
    # 测试用例1：提交新作业
    job1 = {
        "task_groups": [
            {
                "name": "web_server",
                "tasks": [
                    {
                        "name": "nginx",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "nginx:latest",
                            "port": 80
                        }
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("\n测试1：提交新作业")
    result1 = submit_job(job1)
    print(f"结果：{json.dumps(result1, indent=2, ensure_ascii=False)}")
    
    if "job_id" not in result1 or "evaluation_id" not in result1:
        print("错误：作业提交失败，缺少job_id或evaluation_id")
        return
        
    time.sleep(10)  # 等待作业处理
    
    # 测试用例2：更新已有作业
    job1_updated = {
        "task_groups": [
            {
                "name": "web_server",
                "tasks": [
                    {
                        "name": "nginx",
                        "resources": {
                            "cpu": 0,  # 增加CPU需求
                            "memory": 0  # 增加内存需求
                        },
                        "config": {
                            "image": "nginx:latest",
                            "port": 8000
                        }
                    },
                    {
                        "name": "logger",  # 添加新任务
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "fluentd:latest"
                        }
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("\n测试2：更新已有作业")
    result2 = update_job(result1["job_id"], job1_updated)
    print(f"结果：{json.dumps(result2, indent=2, ensure_ascii=False)}")
    
    time.sleep(10)  # 等待作业更新处理
    
    # 测试用例3：提交多任务组作业
    job2 = {
        "task_groups": [
            {
                "name": "web_frontend",
                "tasks": [
                    {
                        "name": "nginx",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "nginx:latest",
                            "port": 8000
                        }
                    },
                    {
                        "name": "node",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "node:latest",
                            "port": 3000
                        }
                    }
                ]
            },
            {
                "name": "database",
                "tasks": [
                    {
                        "name": "mysql",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "mysql:latest",
                            "port": 3306
                        }
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("\n测试3：提交多任务组作业")
    result3 = submit_job(job2)
    print(f"结果：{json.dumps(result3, indent=2, ensure_ascii=False)}")
    
    time.sleep(10)  # 等待作业处理
    
    # 测试用例4：更新多任务组作业
    job2_updated = {
        "task_groups": [
            {
                "name": "web_frontend",
                "tasks": [
                    {
                        "name": "nginx",
                        "resources": {
                            "cpu": 0,  # 增加CPU需求
                            "memory": 0  # 增加内存需求
                        },
                        "config": {
                            "image": "nginx:latest",
                            "port": 8000
                        }
                    },
                    {
                        "name": "node",
                        "resources": {
                            "cpu": 0,  # 增加CPU需求
                            "memory": 0  # 增加内存需求
                        },
                        "config": {
                            "image": "node:latest",
                            "port": 3000
                        }
                    }
                ]
            },
            {
                "name": "database",
                "tasks": [
                    {
                        "name": "mysql",
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "mysql:latest",
                            "port": 3306
                        }
                    },
                    {
                        "name": "backup",  # 添加新任务
                        "resources": {
                            "cpu": 0,
                            "memory": 0
                        },
                        "config": {
                            "image": "busybox:latest",
                            "command": "echo 'Backup completed' > /backup.log"
                        }
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("\n测试4：更新多任务组作业")
    result4 = update_job(result3["job_id"], job2_updated)
    print(f"结果：{json.dumps(result4, indent=2, ensure_ascii=False)}")
    
    time.sleep(10)  # 等待作业更新处理
    
    # # 测试用例5：停止作业
    # print("\n测试5：停止作业")
    # print("停止第一个作业（job0）...")
    # stop_result0 = stop_job(result0["job_id"])
    # print(f"结果：{json.dumps(stop_result0, indent=2, ensure_ascii=False)}")
    
    # time.sleep(10)  # 等待作业停止处理
    
    # print("停止第二个作业（job1）...")
    # stop_result1 = stop_job(result1["job_id"])
    # print(f"结果：{json.dumps(stop_result1, indent=2, ensure_ascii=False)}")
    
    # time.sleep(10)  # 等待作业停止处理
    
    # print("停止第三个作业（job2）...")
    # stop_result2 = stop_job(result3["job_id"])
    # print(f"结果：{json.dumps(stop_result2, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务器，请确保server.py正在运行") 