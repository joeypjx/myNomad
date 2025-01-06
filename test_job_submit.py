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
    #             "cpu": 500,
    #             "memory": 1024
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
                "cpu": 300,
                "memory": 512
            },
            {
                "name": "database",
                "cpu": 200,
                "memory": 512
            }
        ],
        "constraints": {
            "region": "us-west"
        }
    }
    
    print("测试2：提交多个任务组的作业")
    result2 = submit_job(job2)
    print(f"结果：{json.dumps(result2, indent=2, ensure_ascii=False)}\n")
    
    # time.sleep(20)
    
    # # 测试用例3：提交高资源需求的作业
    # job3 = {
    #     "task_groups": [
    #         {
    #             "name": "big_data_processing",
    #             "cpu": 2000,
    #             "memory": 8192
    #         }
    #     ],
    #     "constraints": {
    #         "region": "us-west"
    #     }
    # }
    
    # print("测试3：提交高资源需求的作业")
    # result3 = submit_job(job3)
    # print(f"结果：{json.dumps(result3, indent=2, ensure_ascii=False)}\n")
    
    # # 测试用例4：提交无效的作业（缺少必要字段）
    # job4 = {
    #     "constraints": {
    #         "region": "us-west"
    #     }
    # }
    
    # print("测试4：提交无效的作业（缺少task_groups字段）")
    # try:
    #     result4 = submit_job(job4)
    #     print(f"结果：{json.dumps(result4, indent=2, ensure_ascii=False)}")
    # except Exception as e:
    #     print(f"预期的错误：{str(e)}")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务器，请确保nomad_server.py正在运行") 