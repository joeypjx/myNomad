from typing import List, Dict, Optional, Tuple
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

    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取作业信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "job_id": row[0],
                    "task_groups": json.loads(row[1]),
                    "constraints": json.loads(row[2]),
                    "status": row[3]
                }
            return None
        finally:
            conn.close()

    def get_job_allocations(self, job_id: str) -> List[Dict]:
        """获取作业的所有分配"""
        print(f"[NodeManager] 获取作业 {job_id} 的所有分配")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT allocation_id, node_id, task_group, status
            FROM allocations
            WHERE job_id = ?
        ''', (job_id,))
        allocations = cursor.fetchall()

        conn.commit()
        conn.close()
        return [
            {
                "allocation_id": row[0],
                "node_id": row[1],
                "task_group": row[2],
                "status": row[3]
            }
            for row in allocations
        ]

    def submit_job(self, job_data: Dict) -> Tuple[str, bool]:
        """提交新作业或更新现有作业"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查是否是现有作业的更新
            job_id = job_data.get("job_id")
            is_update = False
            
            if job_id:
                # 检查作业是否存在
                cursor.execute('SELECT 1 FROM jobs WHERE job_id = ?', (job_id,))
                if cursor.fetchone():
                    is_update = True
            else:
                job_id = str(uuid.uuid4())
            
            print(f"\n[NodeManager] {'更新' if is_update else '提交新'}作业，作业ID: {job_id}")
            print(f"[NodeManager] 作业详情: {json.dumps(job_data, indent=2, ensure_ascii=False)}")
            
            cursor.execute('''
                INSERT OR REPLACE INTO jobs (job_id, task_groups, constraints, status)
                VALUES (?, ?, ?, ?)
            ''', (
                job_id,
                json.dumps(job_data["task_groups"]),
                json.dumps(job_data.get("constraints", {})),
                JobStatus.PENDING.value
            ))
            
            conn.commit()
            conn.close()
            print(f"[NodeManager] 作业已{'更新' if is_update else '保存'}到数据库")
            return job_id, is_update
        except Exception as e:
            print(f"[NodeManager] 提交作业时出错: {e}")
            return None, False

    def update_allocation(self, allocation: Allocation) -> bool:
        """更新分配状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO allocations (allocation_id, job_id, node_id, task_group, status)
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

    def delete_allocation(self, allocation_id: str) -> bool:
        """删除分配"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 先获取分配信息
            cursor.execute('''
                SELECT node_id, allocation_id
                FROM allocations
                WHERE allocation_id = ?
            ''', (allocation_id,))
            row = cursor.fetchone()
            
            if row:
                node_id = row[0]
                # 通知节点停止任务
                if hasattr(self, 'agent_client'):
                    success = self.agent_client.stop_allocation(node_id, allocation_id)
                    if not success:
                        print(f"[NodeManager] 警告：通知节点停止分配失败: {allocation_id}")
            
            # 从数据库中删除分配
            cursor.execute('DELETE FROM allocations WHERE allocation_id = ?', (allocation_id,))
            conn.commit()
            conn.close()
            print(f"[NodeManager] 删除分配成功: {allocation_id}")
            return True
        except Exception as e:
            print(f"[NodeManager] 删除分配时出错: {e}")
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

    def stop_job(self, job_id: str) -> bool:
        """停止作业
        1. 获取作业的所有分配
        2. 通知相关节点停止任务
        3. 删除分配记录
        4. 更新作业状态
        """
        try:
            print(f"\n[NodeManager] 开始停止作业: {job_id}")
            
            # 获取作业的所有分配
            allocations = self.get_job_allocations(job_id)
            if not allocations:
                print(f"[NodeManager] 作业 {job_id} 没有活跃的分配")
            
            # 停止所有分配
            for allocation in allocations:
                if hasattr(self, 'agent_client'):
                    success = self.agent_client.stop_allocation(
                        allocation["node_id"], 
                        allocation["allocation_id"]
                    )
                    if not success:
                        print(f"[NodeManager] 警告：通知节点停止分配失败: {allocation['allocation_id']}")
                
                # 无论通知成功与否，都删除分配记录
                self.delete_allocation(allocation["allocation_id"])
            
            # 更新作业状态
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs 
                SET status = ? 
                WHERE job_id = ?
            ''', (JobStatus.COMPLETE.value, job_id))
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 作业 {job_id} 已停止")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 停止作业时出错: {e}")
            return False 