from typing import List, Dict
import threading
import time
import json
import sqlite3
import uuid
from models import JobStatus, Allocation

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
            print(f"[NodeManager] 节点 {node_data['node_id']} 注册成功")
            return True
        except Exception as e:
            print(f"[NodeManager] 注册节点时出错: {e}")
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
            print(f"[NodeManager] 更新心跳时出错: {e}")
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
                allocation.task_group.name,
                allocation.status.value
            ))
            
            conn.commit()
            conn.close()
            print(f"[NodeManager] 更新分配状态成功: {allocation.id}")
            return True
        except Exception as e:
            print(f"[NodeManager] 更新分配状态时出错: {e}")
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
                    print(f"[NodeManager] 标记 {cursor.rowcount} 个节点为不健康状态（心跳超时）")
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[NodeManager] 健康检查时出错: {e}")
            
            time.sleep(5) 