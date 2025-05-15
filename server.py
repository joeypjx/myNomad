from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from allocation_executor import AllocationExecutor
from scheduler import Scheduler
from node_manager import NodeManager
from resource_manager import ResourceManager
import os

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 初始化组件 - 按照正确的顺序创建并解决依赖
node_manager = NodeManager()
resource_manager = ResourceManager(node_manager)
allocation_executor = AllocationExecutor(node_manager)
scheduler = Scheduler(node_manager)
scheduler.set_executor(allocation_executor)

print("[Server] 所有组件初始化完成，服务准备就绪")

# 测试环境的密钥
TEST_API_KEY = os.getenv('TEST_API_KEY', 'test_key_123')

@app.route('/test/clear-all', methods=['POST'])
def clear_all_data():
    """清空所有数据的测试接口"""
    print("\n[API] 收到清空数据请求")
    
    # 验证API密钥
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != TEST_API_KEY:
        print("[API] 错误：无效的API密钥")
        return jsonify({"error": "Invalid API key"}), 401
    
    try:
        # 清空所有数据
        node_manager.clear_all_data()
        print("[API] 所有数据已清空")
        return jsonify({
            "message": "所有数据已清空",
            "cleared_items": {
                "jobs": "所有作业",
                "nodes": "所有节点",
                "templates": "所有模板",
                "allocations": "所有分配"
            }
        }), 200
    except Exception as e:
        print(f"[API] 清空数据时出错: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/register', methods=['POST'])
def register_node():
    """处理节点注册请求"""
    print("\n[API] 收到节点注册请求")
    data = request.get_json()
    if not data:
        print("[API] 错误：未提供节点数据")
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ["node_id", "ip_address", "resources", "healthy", "endpoint"]
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
    
    success = resource_manager.handle_heartbeat(data)
    if success:
        return jsonify({"message": "Heartbeat received"}), 200
    else:
        return jsonify({"error": "Failed to process heartbeat"}), 500

@app.route('/templates', methods=['POST'])
def create_template():
    """创建新的作业模板"""
    print("\n[API] 收到创建作业模板请求")
    data = request.get_json()
    if not data:
        print("[API] 错误：未提供模板数据")
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ["name", "task_groups"]
    if not all(field in data for field in required_fields):
        print("[API] 错误：缺少必要字段")
        return jsonify({"error": "Missing required fields"}), 400
    
    success, result = node_manager.create_job_template(data)
    if success:
        print(f"[API] 成功创建作业模板: {result}")
        return jsonify({
            "template_id": result,
            "message": "作业模板创建成功"
        }), 200
    else:
        print(f"[API] 创建作业模板失败: {result}")
        return jsonify({"error": result}), 500

@app.route('/templates', methods=['GET'])
def list_templates():
    """获取所有作业模板"""
    print("\n[API] 收到获取作业模板列表请求")
    templates = node_manager.list_job_templates()
    return jsonify({
        "templates": templates,
        "count": len(templates)
    })

@app.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """获取特定作业模板详情"""
    print(f"\n[API] 收到获取作业模板详情请求: {template_id}")
    template = node_manager.get_job_template(template_id)
    if not template:
        return jsonify({"error": "模板不存在"}), 404
    return jsonify(template)

@app.route('/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """更新作业模板"""
    print(f"\n[API] 收到更新作业模板请求: {template_id}")
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    success = node_manager.update_job_template(template_id, data)
    if success:
        return jsonify({
            "message": "作业模板更新成功"
        }), 200
    else:
        return jsonify({"error": "更新作业模板失败"}), 500

@app.route('/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """删除作业模板"""
    print(f"\n[API] 收到删除作业模板请求: {template_id}")
    success = node_manager.delete_job_template(template_id)
    if success:
        return jsonify({
            "message": "作业模板删除成功"
        }), 200
    else:
        return jsonify({"error": "删除作业模板失败"}), 500

@app.route('/jobs', methods=['POST'])
def submit_job():
    """提交作业"""
    print("\n[API] 收到新的作业提交请求")
    data = request.get_json()
    if not data:
        print("[API] 错误：未提供作业数据")
        return jsonify({"error": "No data provided"}), 400
    
    print(f"[API] 作业数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    # 检查是否使用模板
    template_id = data.get("template_id")
    if template_id:
        # 从模板创建作业
        template = node_manager.get_job_template(template_id)
        if not template:
            return jsonify({"error": "指定的模板不存在"}), 404
        
        # 使用模板数据作为基础，允许覆盖特定字段
        job_data = {
            "task_groups": template["task_groups"],
            "constraints": template["constraints"]
        }
        
        # 允许覆盖模板中的字段
        if "task_groups" in data:
            job_data["task_groups"] = data["task_groups"]
        if "constraints" in data:
            job_data["constraints"] = data["constraints"]
    else:
        # 直接使用提交的数据
        required_fields = ["task_groups"]
        if not all(field in data for field in required_fields):
            print("[API] 错误：缺少必要字段")
            return jsonify({"error": "Missing required fields"}), 400
        job_data = data
    
    evaluation = scheduler.create_evaluation(job_data)
    if evaluation:
        print(f"[API] 作业评估已创建，评估ID: {evaluation.id}")
        return jsonify({
            "job_id": evaluation.job.id,
            "evaluation_id": evaluation.id,
            "message": "作业评估已创建并加入队列"
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
    
    print(f"[Server] 作业更新评估已创建: {evaluation.id}")
    
    return jsonify({
        "job_id": job_id,
        "evaluation_id": evaluation.id,
        "message": "作业更新评估已创建并加入队列"
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
    
    print(f"[Server] 作业重启评估已创建: {evaluation.id}")
    
    return jsonify({
        "job_id": job_id,
        "evaluation_id": evaluation.id,
        "message": "作业重启评估已创建并加入队列"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8500) 