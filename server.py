from flask import Flask, request, jsonify
import json
from leader import Leader

# 创建Flask应用
app = Flask(__name__)
leader = Leader()
node_manager = leader.get_node_manager()
scheduler = leader.get_scheduler()

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
        leader.register_agent_endpoint(data["node_id"], data["endpoint"])
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
        leader.enqueue_evaluation(evaluation)
        print(f"[API] 作业评估已加入队列，评估ID: {evaluation.id}")
        return jsonify({"evaluation_id": evaluation.id}), 200
    else:
        print("[API] 作业提交失败")
        return jsonify({"error": "Failed to submit job"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8500) 