from flask import Flask, request, jsonify
from typing import List, Dict, Optional
from enum import Enum
import threading
import time
import queue
import uuid
import json
import sqlite3

class EvaluationStatus(Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

class TriggerEvent(Enum):
    JOB_SUBMIT = "job_submit"
    JOB_UPDATE = "job_update"
    JOB_DEREGISTER = "job_deregister"
    NODE_FAILURE = "node_failure"
    NODE_JOIN = "node_join"

class Job:
    def __init__(self, id: str, task_groups: List[Dict], constraints: Dict):
        self.id = id
        self.task_groups = task_groups
        self.constraints = constraints
        self.status = JobStatus.PENDING

class Allocation:
    def __init__(self, id: str, job_id: str, node_id: str, task_group: str):
        self.id = id
        self.job_id = job_id
        self.node_id = node_id
        self.task_group = task_group
        self.status = JobStatus.PENDING

class Evaluation:
    def __init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Dict]):
        self.id = id
        self.status = EvaluationStatus.PENDING
        self.trigger_event = trigger_event
        self.job = job
        self.nodes = nodes
        self.plan = []
        print(f"[Evaluation] 创建新评估 {id} 用于作业 {job.id}")

    def process(self, node_manager):
        """处理评估，生成分配计划"""
        print(f"\n[Evaluation] 开始处理评估 {self.id}")
        print(f"[Evaluation] 作业 {self.job.id} 包含 {len(self.job.task_groups)} 个任务组")
        
        for task_group in self.job.task_groups:
            print(f"\n[Evaluation] 处理任务组: {task_group['name']}")
            print(f"[Evaluation] 资源需求: CPU {task_group.get('cpu', 0)}, 内存 {task_group.get('memory', 0)}MB")
            
            feasible_nodes = self.feasibility_check(task_group)
            if not feasible_nodes:
                print(f"[Evaluation] 没有找到适合任务组 {task_group['name']} 的节点")
                self.status = EvaluationStatus.FAILED
                return False
                
            print(f"[Evaluation] 找到 {len(feasible_nodes)} 个可用节点")
            ranked_nodes = self.rank_nodes(feasible_nodes)
            print("[Evaluation] 节点排序完成")
            
            self.generate_plan(task_group, ranked_nodes)
        
        if not self.plan:
            print("[Evaluation] 无法生成分配计划")
            self.status = EvaluationStatus.FAILED
            return False
            
        self.status = EvaluationStatus.COMPLETE
        print(f"[Evaluation] 评估完成，生成了 {len(self.plan)} 个分配计划")
        return True

    def feasibility_check(self, task_group: Dict) -> List[Dict]:
        """检查节点的可行性"""
        feasible_nodes = []
        print(f"[Evaluation] 开始节点可行性检查，共有 {len(self.nodes)} 个节点待检查")
        
        for node in self.nodes:
            if not node["healthy"]:
                print(f"[Evaluation] 节点 {node['node_id']} 不健康，跳过")
                continue
                
            if node["region"] != self.job.constraints.get("region"):
                print(f"[Evaluation] 节点 {node['node_id']} 区域不匹配，要求: {self.job.constraints.get('region')}, 实际: {node['region']}")
                continue
            
            resources = json.loads(node["resources"])
            if resources["cpu"] < task_group.get("cpu", 0):
                print(f"[Evaluation] 节点 {node['node_id']} CPU不足，要求: {task_group.get('cpu', 0)}, 可用: {resources['cpu']}")
                continue
                
            if resources["memory"] < task_group.get("memory", 0):
                print(f"[Evaluation] 节点 {node['node_id']} 内存不足，要求: {task_group.get('memory', 0)}, 可用: {resources['memory']}")
                continue
            
            print(f"[Evaluation] 节点 {node['node_id']} 满足要求")
            feasible_nodes.append(node)
            
        return feasible_nodes

    def rank_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """对符合条件的节点进行排名"""
        def get_score(node):
            resources = json.loads(node["resources"])
            return (resources["cpu"], resources["memory"])
        
        return sorted(nodes, key=get_score, reverse=True)

    def generate_plan(self, task_group: Dict, nodes: List[Dict]):
        """生成分配计划"""
        if not nodes:
            return
        
        selected_node = nodes[0]
        allocation = Allocation(
            id=str(uuid.uuid4()),
            job_id=self.job.id,
            node_id=selected_node["node_id"],
            task_group=task_group["name"]
        )
        self.plan.append(allocation)

class NodeManager:
    def __init__(self, db_path: str = "nomad.db"):
        self.db_path = db_path
        self.heartbeat_timeout = 15
        self.setup_database()
        self.check_thread = threading.Thread(target=self._check_node_health, daemon=True)
        self.check_thread.start()

    def setup_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建节点表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                region TEXT,
                resources TEXT,
                healthy INTEGER,
                last_heartbeat REAL
            )
        ''')
        
        # 创建作业表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                task_groups TEXT,
                constraints TEXT,
                status TEXT
            )
        ''')
        
        # 创建分配表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allocations (
                allocation_id TEXT PRIMARY KEY,
                job_id TEXT,
                node_id TEXT,
                task_group TEXT,
                status TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id),
                FOREIGN KEY(node_id) REFERENCES nodes(node_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def register_node(self, node_data: Dict) -> bool:
        """注册新节点"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO nodes (node_id, region, resources, healthy, last_heartbeat)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                node_data["node_id"],
                node_data["region"],
                json.dumps(node_data["resources"]),
                1 if node_data["healthy"] else 0,
                time.time()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error registering node: {e}")
            return False

    def update_heartbeat(self, heartbeat_data: Dict) -> bool:
        """更新节点心跳信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE nodes 
                SET resources = ?, 
                    healthy = ?,
                    last_heartbeat = ?
                WHERE node_id = ?
            ''', (
                json.dumps(heartbeat_data["resources"]),
                1 if heartbeat_data["healthy"] else 0,
                heartbeat_data["timestamp"],
                heartbeat_data["node_id"]
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating heartbeat: {e}")
            return False

    def get_healthy_nodes(self) -> List[Dict]:
        """获取所有健康的节点"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM nodes WHERE healthy = 1')
            rows = cursor.fetchall()
            
            nodes = [{
                "node_id": row[0],
                "region": row[1],
                "resources": row[2],
                "healthy": bool(row[3]),
                "last_heartbeat": row[4]
            } for row in rows]
            
            print(f"[NodeManager] 当前可用节点数量: {len(nodes)}")
            for node in nodes:
                print(f"[NodeManager] 节点 {node['node_id']} - 区域: {node['region']} - 资源: {node['resources']}")
            
            return nodes
        finally:
            conn.close()

    def submit_job(self, job_data: Dict) -> str:
        """提交新作业"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            job_id = str(uuid.uuid4())
            print(f"\n[NodeManager] 正在提交新作业，作业ID: {job_id}")
            print(f"[NodeManager] 作业详情: {json.dumps(job_data, indent=2, ensure_ascii=False)}")
            
            cursor.execute('''
                INSERT INTO jobs (job_id, task_groups, constraints, status)
                VALUES (?, ?, ?, ?)
            ''', (
                job_id,
                json.dumps(job_data["task_groups"]),
                json.dumps(job_data.get("constraints", {})),
                JobStatus.PENDING.value
            ))
            
            conn.commit()
            conn.close()
            print(f"[NodeManager] 作业已保存到数据库")
            return job_id
        except Exception as e:
            print(f"[NodeManager] 提交作业时出错: {e}")
            return None

    def update_allocation(self, allocation: Allocation) -> bool:
        """更新分配状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO allocations (allocation_id, job_id, node_id, task_group, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                allocation.id,
                allocation.job_id,
                allocation.node_id,
                allocation.task_group,
                allocation.status.value
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating allocation: {e}")
            return False

    def _check_node_health(self):
        """检查节点健康状态"""
        while True:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timeout_threshold = time.time() - self.heartbeat_timeout
                cursor.execute('''
                    UPDATE nodes 
                    SET healthy = 0 
                    WHERE last_heartbeat < ? AND healthy = 1
                ''', (timeout_threshold,))
                
                if cursor.rowcount > 0:
                    print(f"Marked {cursor.rowcount} nodes as unhealthy due to timeout")
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error in health check: {e}")
            
            time.sleep(5)

class Scheduler:
    def __init__(self, node_manager: NodeManager):
        self.node_manager = node_manager
        self.evaluation_queue = queue.Queue()
        print("[Scheduler] 调度器已初始化")
        self.scheduling_thread = threading.Thread(target=self._scheduling_loop, daemon=True)
        self.scheduling_thread.start()

    def submit_evaluation(self, job_data: Dict):
        """提交评估请求"""
        print("\n[Scheduler] 收到新的作业评估请求")
        job_id = self.node_manager.submit_job(job_data)
        if not job_id:
            print("[Scheduler] 作业提交失败")
            return None

        print(f"[Scheduler] 开始为作业 {job_id} 创建评估")
        job = Job(job_id, job_data["task_groups"], job_data.get("constraints", {}))
        nodes = self.node_manager.get_healthy_nodes()
        
        if not nodes:
            print("[Scheduler] 警告：没有可用的健康节点")
            return job_id
        
        evaluation = Evaluation(
            id=str(uuid.uuid4()),
            trigger_event=TriggerEvent.JOB_SUBMIT,
            job=job,
            nodes=nodes
        )
        
        print(f"[Scheduler] 创建评估成功，评估ID: {evaluation.id}")
        self.evaluation_queue.put(evaluation)
        return job_id

    def _scheduling_loop(self):
        """调度循环"""
        print("[Scheduler] 调度循环已启动")
        while True:
            if not self.evaluation_queue.empty():
                evaluation = self.evaluation_queue.get()
                print(f"\n[Scheduler] 开始处理评估 {evaluation.id}")
                success = evaluation.process(self.node_manager)
                
                if success:
                    print(f"[Scheduler] 评估 {evaluation.id} 成功，开始更新分配计划")
                    for allocation in evaluation.plan:
                        print(f"[Scheduler] 创建分配: 作业 {allocation.job_id} 的任务组 {allocation.task_group} 分配到节点 {allocation.node_id}")
                        self.node_manager.update_allocation(allocation)
                else:
                    print(f"[Scheduler] 评估 {evaluation.id} 失败，无法为作业创建分配计划")
            
            time.sleep(1)

# 创建Flask应用
app = Flask(__name__)
node_manager = NodeManager()
scheduler = Scheduler(node_manager)

@app.route('/register', methods=['POST'])
def register_node():
    """处理节点注册请求"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ["node_id", "region", "resources", "healthy"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    success = node_manager.register_node(data)
    if success:
        return jsonify({"message": "Node registered successfully"}), 200
    else:
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
    
    job_id = scheduler.submit_evaluation(data)
    if job_id:
        print(f"[API] 作业提交成功，作业ID: {job_id}")
        return jsonify({"job_id": job_id}), 200
    else:
        print("[API] 作业提交失败")
        return jsonify({"error": "Failed to submit job"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8500) 