from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from allocation_executor import AllocationExecutor
from scheduler import Scheduler
from node_manager import NodeManager

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 初始化组件 - 按照正确的顺序创建并解决依赖
node_manager = NodeManager()
allocation_executor = AllocationExecutor(node_manager)
scheduler = Scheduler(node_manager)
scheduler.set_executor(allocation_executor)

print("[Server] 所有组件初始化完成，服务准备就绪")

@app.route('/register', methods=['POST'])
def register_node():
    """处理节点注册请求"""
    print("\n[API] 收到节点注册请求")
    data = request.get_json()
    if not data:
        print("[API] 错误：未提供节点数据")
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ["node_id", "region", "resources", "healthy", "endpoint"]
    if not all(field in data for field in required_fields):
        print("[API] 错误：缺少必要字段")
        return jsonify({"error": "Missing required fields"}), 400
    
    # 注册节点
    success = node_manager.register_node(data)
    if success:
        # 注册agent endpoint
        allocation_executor.register_agent_endpoint(data["node_id"], data["endpoint"])
        print(f"[API] 节点 {data['node_id']} 注册成功")
        return jsonify({"message": "Node registered successfully"}), 200
    else:
        print("[API] 节点注册失败")
        return jsonify({"error": "Failed to register node"}), 500

@app.route('/heartbeat', methods=['POST'])
def handle_heartbeat():
    """处理节点心跳请求"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ["node_id", "resources", "healthy", "timestamp"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    success = node_manager.update_heartbeat(data)
    if success:
        return jsonify({"message": "Heartbeat received"}), 200
    else:
        return jsonify({"error": "Failed to process heartbeat"}), 500

@app.route('/jobs', methods=['POST'])
def submit_job():
    """提交作业"""
    print("\n[API] 收到新的作业提交请求")
    data = request.get_json()
    if not data:
        print("[API] 错误：未提供作业数据")
        return jsonify({"error": "No data provided"}), 400
    
    print(f"[API] 作业数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    required_fields = ["task_groups"]
    if not all(field in data for field in required_fields):
        print("[API] 错误：缺少必要字段")
        return jsonify({"error": "Missing required fields"}), 400
    
    evaluation = scheduler.create_evaluation(data)
    if evaluation:
        scheduler.enqueue_evaluation(evaluation)
        print(f"[API] 作业评估已加入队列，评估ID: {evaluation.id}")
        return jsonify({
            "job_id": evaluation.job.id,
            "evaluation_id": evaluation.id,
            "message": "作业评估已加入队列"
        }), 200
    else:
        print("[API] 作业提交失败")
        return jsonify({"error": "Failed to submit job"}), 500

@app.route('/jobs/<job_id>', methods=['PUT'])
def update_job(job_id):
    """更新作业"""
    data = request.get_json()
    print(f"\n[Server] 收到作业更新请求: {job_id}")
    print(f"[Server] 更新数据: {json.dumps(data, indent=2)}")
    
    # 验证作业是否存在
    job = node_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "作业不存在"}), 404
    
    # 创建评估
    evaluation = scheduler.create_evaluation(data, job_id=job_id)
    if not evaluation:
        return jsonify({"error": "无法创建评估"}), 400
    
    # 将评估加入队列
    scheduler.enqueue_evaluation(evaluation)
    print(f"[Server] 作业更新评估已加入队列: {evaluation.id}")
    
    return jsonify({
        "job_id": job_id,
        "evaluation_id": evaluation.id,
        "message": "作业更新评估已加入队列"
    })

@app.route('/jobs/<job_id>', methods=['DELETE'])
def stop_job(job_id):
    """停止作业"""
    print(f"\n[Server] 收到停止作业请求: {job_id}")
    
    # 验证作业是否存在
    job = node_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "作业不存在"}), 404
    
    # 停止作业，使用AllocationExecutor处理完整的停止流程
    success = allocation_executor.stop_job(job_id)
    if success:
        return jsonify({
            "message": f"作业 {job_id} 已停止"
        }), 200
    else:
        return jsonify({
            "error": f"停止作业 {job_id} 失败"
        }), 500

@app.route('/jobs', methods=['GET'])
def get_jobs():
    """获取所有作业信息"""
    jobs = node_manager.get_all_jobs()
    return jsonify({
        "jobs": jobs,
        "count": len(jobs)
    })

@app.route('/jobs/<job_id>', methods=['GET'])
def get_job_info(job_id):
    """获取指定作业的详细信息"""
    print(f"\n[API] 收到获取作业 {job_id} 的详细信息请求")
    
    job_info = node_manager.get_job_info(job_id)
    if not job_info:
        return jsonify({"error": "作业不存在"}), 404
    
    return jsonify(job_info), 200

@app.route('/nodes', methods=['GET'])
def get_all_nodes():
    """获取所有节点信息"""
    print("\n[API] 收到获取所有节点信息的请求")
    nodes = node_manager.get_all_nodes()
    if nodes is None:
        return jsonify({"error": "获取节点信息失败"}), 500
    
    # 为每个节点添加其当前的分配信息
    nodes_with_allocations = []
    for node in nodes:
        node_allocations = node_manager.get_node_allocations(node["node_id"])
        node["allocations"] = node_allocations
        nodes_with_allocations.append(node)
    
    return jsonify({
        "nodes": nodes_with_allocations,
        "count": len(nodes_with_allocations)
    }), 200

@app.route('/jobs/<job_id>/delete', methods=['POST'])
def delete_job(job_id):
    """删除作业及其所有相关资源"""
    print(f"\n[Server] 收到删除作业请求: {job_id}")
    
    # 验证作业是否存在
    job = node_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "作业不存在"}), 404
    
    # 删除作业及其相关资源，使用AllocationExecutor处理完整的删除流程
    success = allocation_executor.delete_job(job_id)
    if success:
        return jsonify({
            "message": f"作业 {job_id} 及其相关资源已删除"
        }), 200
    else:
        return jsonify({
            "error": f"删除作业 {job_id} 失败"
        }), 500

@app.route('/jobs/<job_id>/restart', methods=['POST'])
def restart_job(job_id):
    """重启已停止的作业"""
    print(f"\n[Server] 收到重启作业请求: {job_id}")
    
    # 验证作业是否存在
    job = node_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "作业不存在"}), 404
    
    # 验证作业状态是否为 dead
    if job.get("status") != "dead":
        return jsonify({"error": "只能重启已停止的作业"}), 400
    
    # 创建评估，但使用原有的作业配置
    job_config = {
        "task_groups": job["task_groups"],
        "constraints": job.get("constraints", {})
    }
    
    evaluation = scheduler.create_evaluation(job_config, job_id=job_id)
    if not evaluation:
        return jsonify({"error": "无法创建评估"}), 400
    
    # 将评估加入队列
    scheduler.enqueue_evaluation(evaluation)
    print(f"[Server] 作业重启评估已加入队列: {evaluation.id}")
    
    return jsonify({
        "job_id": job_id,
        "evaluation_id": evaluation.id,
        "message": "作业重启评估已加入队列"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8500) 