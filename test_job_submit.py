import requests
import json
import time

def submit_job(job_data):
    """提交作业到服务器"""
    response = requests.post(
        "http://localhost:8500/jobs",
        json=job_data,
        headers={"Content-Type": "application/json"}
    )
    return response.json()

def main():
    # # 测试用例1：提交单个任务组的作业
    # job1 = {
    #     "task_groups": [
    #         {
    #             "name": "web_server",
    #             "tasks": [
    #                 {
    #                     "name": "nginx",
    #                     "resources": {
    #                         "cpu": 300,
    #                         "memory": 512
    #                     },
    #                     "config": {
    #                         "image": "nginx:latest",
    #                         "port": 80
    #                     }
    #                 },
    #                 {
    #                     "name": "logger",
    #                     "resources": {
    #                         "cpu": 100,
    #                         "memory": 256
    #                     },
    #                     "config": {
    #                         "image": "fluentd:latest"
    #                     }
    #                 }
    #             ]
    #         }
    #     ],
    #     "constraints": {
    #         "region": "us-west"
    #     }
    # }
    
    # print("测试1：提交单个任务组的作业")
    # result1 = submit_job(job1)
    # print(f"结果：{json.dumps(result1, indent=2, ensure_ascii=False)}\n")
    
    # time.sleep(20)  # 等待一段时间再提交下一个作业
    
    # 测试用例2：提交多个任务组的作业
    job2 = {
        "task_groups": [
            {
                "name": "web_frontend",
                "tasks": [
                    {
                        "name": "nginx",
                        "resources": {
                            "cpu": 200,
                            "memory": 256
                        },
                        "config": {
                            "image": "nginx:latest",
                            "port": 80
                        }
                    },
                    {
                        "name": "node",
                        "resources": {
                            "cpu": 100,
                            "memory": 256
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
                            "cpu": 500,
                            "memory": 1024
                        },
                        "config": {
                            "image": "mysql:latest",
                            "port": 3306
                        }
                    },
                    {
                        "name": "backup",
                        "resources": {
                            "cpu": 100,
                            "memory": 256
                        },
                        "config": {
                            "image": "backup-tool:latest"
                        }
                    }
                ]
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("测试2：提交多个任务组的作业")
    result2 = submit_job(job2)
    print(f"结果：{json.dumps(result2, indent=2, ensure_ascii=False)}\n")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务器，请确保nomad_server.py正在运行") 