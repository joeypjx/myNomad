from typing import List, Dict, Optional, Tuple
import time
import json
import sqlite3
import uuid
from models import JobStatus, Allocation

class NodeManager:
    def __init__(self, db_path: str = "nomad.db"):
        self.db_path = db_path
        self.setup_database()
        print("[NodeManager] 节点管理器已初始化")

    def setup_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建节点表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                ip_address TEXT,
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
                start_time REAL,
                end_time REAL,
                last_update REAL,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id),
                FOREIGN KEY(node_id) REFERENCES nodes(node_id)
            )
        ''')
        
        # 创建任务状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_status (
                allocation_id TEXT,
                task_name TEXT,
                resources TEXT,
                config TEXT,
                status TEXT,
                start_time REAL,
                end_time REAL,
                error TEXT,
                exit_code INTEGER,
                last_update REAL,
                message TEXT,
                PRIMARY KEY (allocation_id, task_name),
                FOREIGN KEY(allocation_id) REFERENCES allocations(allocation_id)
            )
        ''')

        # 创建作业模板表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_templates (
                template_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                task_groups TEXT NOT NULL,
                constraints TEXT,
                created_at REAL,
                updated_at REAL
            )
        ''')
        
        conn.commit()
        conn.close()

    def register_node(self, node_data: Dict) -> bool:
        """注册新节点"""
        try:
            # 检查必要字段
            required_fields = ["node_id", "ip_address", "resources", "healthy"]
            if not all(field in node_data for field in required_fields):
                print(f"[NodeManager] 注册节点时缺少必要字段: {required_fields}")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO nodes (node_id, ip_address, resources, healthy, last_heartbeat)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                node_data["node_id"],
                node_data["ip_address"],
                json.dumps(node_data["resources"]),
                1 if node_data["healthy"] else 0,
                time.time()
            ))
            
            conn.commit()
            conn.close()
            print(f"[NodeManager] 节点 {node_data['node_id']} (IP: {node_data['ip_address']}) 注册成功")
            return True
        except Exception as e:
            print(f"[NodeManager] 注册节点时出错: {e}")
            return False

    def update_heartbeat(self, heartbeat_data: Dict) -> bool:
        """更新节点心跳信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 更新节点信息
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
            
            # 更新分配状态
            if "allocations" in heartbeat_data:
                for allocation_id, allocation_status in heartbeat_data["allocations"].items():
                    # 更新分配状态
                    cursor.execute('''
                        UPDATE allocations 
                        SET status = ?,
                            start_time = ?,
                            end_time = ?,
                            last_update = ?
                        WHERE allocation_id = ?
                    ''', (
                        allocation_status["status"],
                        allocation_status["start_time"],
                        allocation_status["end_time"],
                        heartbeat_data["timestamp"],
                        allocation_id
                    ))
                    
                    # 更新任务状态
                    for task_name, task_status in allocation_status["tasks"].items():
                        cursor.execute('''
                            INSERT OR REPLACE INTO task_status
                            (allocation_id, task_name, status, start_time, end_time, error, exit_code, last_update, message)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            allocation_id,
                            task_name,
                            task_status["status"],
                            task_status["start_time"],
                            task_status["end_time"],
                            task_status.get("error"),
                            task_status.get("exit_code"),
                            heartbeat_data["timestamp"],
                            task_status.get("message")
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
                "ip_address": row[1],
                "resources": row[2],
                "healthy": bool(row[3]),
                "last_heartbeat": row[4]
            } for row in rows]
            
            print(f"[NodeManager] 当前可用节点数量: {len(nodes)}")
            for node in nodes:
                print(f"[NodeManager] 节点 {node['node_id']} - IP: {node['ip_address']} - 资源: {node['resources']}")
            
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
            current_status = JobStatus.PENDING.value  # 默认为PENDING，用于新作业
            
            if job_id:
                # 检查作业是否存在
                cursor.execute('SELECT status FROM jobs WHERE job_id = ?', (job_id,))
                row = cursor.fetchone()
                if row:
                    is_update = True
                    current_status = row[0]  # 获取当前状态
            else:
                job_id = str(uuid.uuid4())
            
            print(f"\n[NodeManager] {'更新' if is_update else '提交新'}作业，作业ID: {job_id}")
            print(f"[NodeManager] 作业详情: {json.dumps(job_data, indent=2, ensure_ascii=False)}")
            
            # 使用适当的状态：对于更新保留当前状态，对于新作业使用PENDING
            status_to_use = current_status
            
            cursor.execute('''
                INSERT OR REPLACE INTO jobs (job_id, task_groups, constraints, status)
                VALUES (?, ?, ?, ?)
            ''', (
                job_id,
                json.dumps(job_data["task_groups"]),
                json.dumps(job_data.get("constraints", {})),
                status_to_use
            ))
            
            conn.commit()
            conn.close()
            print(f"[NodeManager] 作业已{'更新' if is_update else '保存'}到数据库 (状态: {status_to_use})")
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
            
            # 更新作业状态
            self.update_job_status(allocation.job_id)
            return True
        except Exception as e:
            print(f"[NodeManager] 更新分配状态时出错: {e}")
            return False

    def delete_allocation(self, allocation_id: str, notify_agent: bool = True) -> Tuple[bool, Optional[str]]:
        """删除分配
        Args:
            allocation_id: 分配ID
            notify_agent: 是否需要通知agent停止任务，默认为True
        
        Returns:
            Tuple[bool, Optional[str]]: 第一个元素表示操作是否成功，第二个元素是需要通知的节点ID（如果notify_agent为True）
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            node_id_to_notify = None
            
            # 先获取分配信息
            cursor.execute('''
                SELECT node_id, allocation_id
                FROM allocations
                WHERE allocation_id = ?
            ''', (allocation_id,))
            row = cursor.fetchone()
            
            if row and notify_agent:
                node_id_to_notify = row[0]
            
            # 从数据库中删除分配
            cursor.execute('DELETE FROM allocations WHERE allocation_id = ?', (allocation_id,))
            conn.commit()
            conn.close()
            print(f"[NodeManager] 删除分配成功: {allocation_id}")
            return True, node_id_to_notify
        except Exception as e:
            print(f"[NodeManager] 删除分配时出错: {e}")
            return False, None

    def stop_job(self, job_id: str) -> Tuple[bool, List[Dict]]:
        """停止作业
        1. 获取作业的所有分配
        2. 返回分配信息供执行层处理
        3. 更新作业状态为 DEAD
        
        Returns:
            Tuple[bool, List[Dict]]: (操作是否成功, 需要停止的分配列表)
        """
        try:
            print(f"\n[NodeManager] 开始停止作业: {job_id}")
            
            # 获取作业的所有分配
            allocations = self.get_job_allocations(job_id)
            if not allocations:
                print(f"[NodeManager] 作业 {job_id} 没有活跃的分配")
            
            # 更新作业状态为 DEAD
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs 
                SET status = ? 
                WHERE job_id = ?
            ''', (JobStatus.DEAD.value, job_id))
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 作业 {job_id} 状态已更新为DEAD")
            # 返回所有分配信息，由调用者负责停止分配
            return True, allocations
            
        except Exception as e:
            print(f"[NodeManager] 停止作业时出错: {e}")
            return False, []

    def get_all_jobs(self):
        """获取所有作业信息"""
        try:
            # 创建数据库连接
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有作业
            cursor.execute("SELECT job_id, task_groups, constraints, status FROM jobs")
            jobs = cursor.fetchall()
            
            jobs_info = []
            for job in jobs:
                job_id, task_groups, constraints, status = job
                
                # 获取作业的所有分配信息
                cursor.execute("""
                    SELECT allocation_id, node_id, task_group, status, start_time, end_time 
                    FROM allocations 
                    WHERE job_id = ?
                """, (job_id,))
                allocations = cursor.fetchall()
                
                allocations_info = []
                for alloc in allocations:
                    allocation_id, node_id, task_group, alloc_status, start_time, end_time = alloc
                    
                    # 获取分配的所有任务信息
                    cursor.execute("""
                        SELECT task_name, resources, config, status, start_time, end_time, exit_code, message
                        FROM task_status
                        WHERE allocation_id = ?
                    """, (allocation_id,))
                    tasks = cursor.fetchall()
                    
                    tasks_info = {}
                    for task in tasks:
                        name, resources, config, task_status, task_start, task_end, exit_code, message = task
                        tasks_info[name] = {
                            "resources": json.loads(resources) if resources else {},
                            "config": json.loads(config) if config else {},
                            "status": task_status,
                            "start_time": task_start,
                            "end_time": task_end,
                            "exit_code": exit_code,
                            "message": message
                        }
                    
                    allocations_info.append({
                        "allocation_id": allocation_id,
                        "node_id": node_id,
                        "task_group": task_group,
                        "status": alloc_status,
                        "start_time": start_time,
                        "end_time": end_time,
                        "tasks": tasks_info
                    })
                
                jobs_info.append({
                    "job_id": job_id,
                    "task_groups": json.loads(task_groups),
                    "constraints": json.loads(constraints),
                    "status": status,
                    "allocations": allocations_info
                })
            
            conn.close()
            return jobs_info
            
        except Exception as e:
            print(f"获取作业信息时出错: {str(e)}")
            return []

    def get_all_nodes(self) -> Optional[List[Dict]]:
        """获取所有节点信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT node_id, ip_address, resources, healthy, last_heartbeat 
                FROM nodes
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            nodes = []
            for row in rows:
                nodes.append({
                    "node_id": row[0],
                    "ip_address": row[1],
                    "resources": json.loads(row[2]),
                    "healthy": bool(row[3]),
                    "last_heartbeat": row[4]
                })
            return nodes
        except Exception as e:
            print(f"[NodeManager] 获取所有节点信息时出错: {e}")
            return None

    def get_node_allocations(self, node_id: str) -> List[Dict]:
        """获取节点的所有分配"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT allocation_id, job_id, task_group, status, start_time, end_time
                FROM allocations
                WHERE node_id = ?
            ''', (node_id,))
            rows = cursor.fetchall()
            conn.close()
            
            allocations = []
            for row in rows:
                allocations.append({
                    "allocation_id": row[0],
                    "job_id": row[1],
                    "task_group": row[2],
                    "status": row[3],
                    "start_time": row[4],
                    "end_time": row[5]
                })
            return allocations
        except Exception as e:
            print(f"[NodeManager] 获取节点分配信息时出错: {e}")
            return []

    def get_job_info(self, job_id: str) -> Optional[Dict]:
        """获取作业详细信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取作业基本信息
            cursor.execute('''
                SELECT job_id, task_groups, constraints, status 
                FROM jobs 
                WHERE job_id = ?
            ''', (job_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
                
            job_info = {
                "job_id": row[0],
                "task_groups": json.loads(row[1]),
                "constraints": json.loads(row[2]),
                "status": row[3]
            }
            
            # 获取作业的所有分配
            cursor.execute('''
                SELECT allocation_id, node_id, task_group, status, start_time, end_time
                FROM allocations
                WHERE job_id = ?
            ''', (job_id,))
            allocations = cursor.fetchall()
            
            # 处理分配信息
            allocations_info = []
            for alloc in allocations:
                allocation_id, node_id, task_group, status, start_time, end_time = alloc
                allocations_info.append({
                    "allocation_id": allocation_id,
                    "node_id": node_id,
                    "task_group": task_group,
                    "status": status,
                    "start_time": start_time,
                    "end_time": end_time
                })
            
            job_info["allocations"] = allocations_info
            conn.close()
            return job_info
            
        except Exception as e:
            print(f"[NodeManager] 获取作业信息时出错: {e}")
            return None 

    def update_job_status(self, job_id: str) -> bool:
        """
        更新作业状态
        根据作业的所有分配状态来确定作业的整体状态
        """
        try:
            # 获取作业的所有分配
            allocations = self.get_job_allocations(job_id)
            if not allocations:
                return True

            # 统计各种状态的分配数量
            status_counts = {
                "pending": 0,
                "running": 0,
                "complete": 0,
                "failed": 0,
                "lost": 0,
                "stopped": 0
            }

            for alloc in allocations:
                status = alloc["status"].lower()
                if status in status_counts:
                    status_counts[status] += 1

            total_allocations = len(allocations)
            new_status = None

            # 确定作业的新状态
            if status_counts["lost"] == total_allocations:
                new_status = JobStatus.LOST
            elif status_counts["failed"] == total_allocations:
                new_status = JobStatus.FAILED
            elif status_counts["running"] > 0:
                if status_counts["failed"] > 0 or status_counts["lost"] > 0:
                    new_status = JobStatus.DEGRADED
                else:
                    new_status = JobStatus.RUNNING
            elif status_counts["pending"] == total_allocations:
                # 检查是否因资源不足而被阻塞
                if not self._has_sufficient_resources(job_id):
                    new_status = JobStatus.BLOCKED
                else:
                    new_status = JobStatus.PENDING
            elif status_counts["complete"] + status_counts["stopped"] == total_allocations:
                new_status = JobStatus.COMPLETE

            if new_status:
                # 更新数据库中的作业状态
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE jobs 
                    SET status = ? 
                    WHERE job_id = ?
                ''', (new_status.value, job_id))
                conn.commit()
                conn.close()
                print(f"[NodeManager] 作业 {job_id} 状态更新为: {new_status.value}")
            
            return True

        except Exception as e:
            print(f"[NodeManager] 更新作业状态时出错: {e}")
            return False

    def _has_sufficient_resources(self, job_id: str) -> bool:
        """
        检查是否有足够的资源来运行作业
        直接从数据库获取节点资源信息
        """
        try:
            # 获取作业信息
            job_info = self.get_job_info(job_id)
            if not job_info:
                print(f"[NodeManager] 找不到作业 {job_id} 的信息")
                return False

            # 直接从数据库获取所有健康的节点
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT node_id, resources 
                FROM nodes 
                WHERE healthy = 1
            ''')
            healthy_nodes = cursor.fetchall()
            conn.close()
            
            if not healthy_nodes:
                print("[NodeManager] 没有健康的节点可用于资源检查")
                return False

            # 检查每个任务组的资源需求
            for task_group in job_info["task_groups"]:
                total_cpu = 0
                total_memory = 0
                for task in task_group["tasks"]:
                    total_cpu += task["resources"].get("cpu", 0)
                    total_memory += task["resources"].get("memory", 0)

                # 检查是否有节点满足资源要求
                resource_satisfied = False
                for node_id, resources_json in healthy_nodes:
                    node_resources = json.loads(resources_json)
                    # 计算节点可用资源 (简化逻辑，实际应考虑正在运行的分配)
                    available_cpu = node_resources.get("cpu", 0)
                    available_memory = node_resources.get("memory", 0)
                    
                    # 查询节点上运行的分配，计算已用资源
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT a.allocation_id, ts.resources
                        FROM allocations a
                        JOIN task_status ts ON a.allocation_id = ts.allocation_id
                        WHERE a.node_id = ? AND a.status = 'running'
                    ''', (node_id,))
                    running_tasks = cursor.fetchall()
                    conn.close()
                    
                    # 计算已使用的资源
                    used_cpu = 0
                    used_memory = 0
                    for _, task_resources_json in running_tasks:
                        if task_resources_json:
                            task_resources = json.loads(task_resources_json)
                            used_cpu += task_resources.get("cpu", 0)
                            used_memory += task_resources.get("memory", 0)
                    
                    # 计算实际可用资源
                    available_cpu -= used_cpu
                    available_memory -= used_memory
                    
                    if (available_cpu >= total_cpu and available_memory >= total_memory):
                        resource_satisfied = True
                        break

                if not resource_satisfied:
                    print(f"[NodeManager] 作业 {job_id} 的任务组资源需求无法满足：CPU={total_cpu}, 内存={total_memory}")
                    return False

            print(f"[NodeManager] 作业 {job_id} 的资源需求可以满足")
            return True

        except Exception as e:
            print(f"[NodeManager] 检查资源时出错: {e}")
            return False 

    def delete_job(self, job_id: str) -> bool:
        """删除作业及其所有相关资源
        
        注意：此方法已被弃用，请直接使用AllocationExecutor.delete_job
        此方法仅保留用于向后兼容性
        """
        print(f"\n[NodeManager] 警告：直接使用NodeManager.delete_job方法已被弃用")
        print(f"[NodeManager] 建议使用AllocationExecutor.delete_job来代替")
            
        # 兼容性逻辑 - 之前的方法依赖于stop_job，但现在stop_job不再执行实际操作
        # 因此需要手动处理数据库清理
        try:
            # 这个方法不再调用stop_job来删除allocation，而是直接从数据库中删除记录
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有相关的allocation_ids
            cursor.execute('SELECT allocation_id FROM allocations WHERE job_id = ?', (job_id,))
            allocation_ids = [row[0] for row in cursor.fetchall()]
            
            # 删除相关的task_status记录
            for allocation_id in allocation_ids:
                cursor.execute('DELETE FROM task_status WHERE allocation_id = ?', (allocation_id,))
                print(f"[NodeManager] 删除allocation {allocation_id}的任务状态记录")
            
            # 删除allocation记录
            cursor.execute('DELETE FROM allocations WHERE job_id = ?', (job_id,))
            print(f"[NodeManager] 删除作业 {job_id} 的所有分配记录")
            
            # 删除job记录
            cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            print(f"[NodeManager] 删除作业 {job_id} 记录")
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 作业 {job_id} 及其相关资源已完全删除")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 删除作业时出错: {e}")
            return False 

    def clean_job_data(self, job_id: str) -> bool:
        """清理作业相关的所有数据库记录
        
        注意：此方法只负责数据库清理，不涉及停止运行中的任务或与Agent通信
        这应该由AllocationExecutor在调用此方法前处理
        
        Args:
            job_id: 要清理的作业ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有相关的allocation_ids
            cursor.execute('SELECT allocation_id FROM allocations WHERE job_id = ?', (job_id,))
            allocation_ids = [row[0] for row in cursor.fetchall()]
            
            # 删除相关的task_status记录
            for allocation_id in allocation_ids:
                cursor.execute('DELETE FROM task_status WHERE allocation_id = ?', (allocation_id,))
                print(f"[NodeManager] 删除allocation {allocation_id}的任务状态记录")
            
            # 删除allocation记录
            cursor.execute('DELETE FROM allocations WHERE job_id = ?', (job_id,))
            print(f"[NodeManager] 删除作业 {job_id} 的所有分配记录")
            
            # 删除job记录
            cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            print(f"[NodeManager] 删除作业 {job_id} 记录")
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 作业 {job_id} 的所有数据库记录已清理")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 清理作业数据时出错: {e}")
            return False 

    def create_job_template(self, template_data: Dict) -> Tuple[bool, str]:
        """创建新的作业模板
        
        Args:
            template_data: 包含模板信息的字典，必须包含name和task_groups字段
            
        Returns:
            Tuple[bool, str]: (是否成功, 模板ID或错误信息)
        """
        try:
            if not template_data.get("name") or not template_data.get("task_groups"):
                return False, "模板名称和任务组配置是必需的"
                
            template_id = str(uuid.uuid4())
            current_time = time.time()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO job_templates 
                (template_id, name, description, task_groups, constraints, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                template_id,
                template_data["name"],
                template_data.get("description", ""),
                json.dumps(template_data["task_groups"]),
                json.dumps(template_data.get("constraints", {})),
                current_time,
                current_time
            ))
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 成功创建作业模板: {template_id}")
            return True, template_id
            
        except Exception as e:
            print(f"[NodeManager] 创建作业模板时出错: {e}")
            return False, str(e)

    def get_job_template(self, template_id: str) -> Optional[Dict]:
        """获取作业模板详情"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT template_id, name, description, task_groups, constraints, created_at, updated_at
                FROM job_templates
                WHERE template_id = ?
            ''', (template_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "template_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "task_groups": json.loads(row[3]),
                    "constraints": json.loads(row[4]),
                    "created_at": row[5],
                    "updated_at": row[6]
                }
            return None
            
        except Exception as e:
            print(f"[NodeManager] 获取作业模板时出错: {e}")
            return None

    def list_job_templates(self) -> List[Dict]:
        """获取所有作业模板"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT template_id, name, description, created_at, updated_at
                FROM job_templates
                ORDER BY created_at DESC
            ''')
            
            templates = []
            for row in cursor.fetchall():
                templates.append({
                    "template_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "updated_at": row[4]
                })
            
            conn.close()
            return templates
            
        except Exception as e:
            print(f"[NodeManager] 获取作业模板列表时出错: {e}")
            return []

    def update_job_template(self, template_id: str, template_data: Dict) -> bool:
        """更新作业模板"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查模板是否存在
            cursor.execute('SELECT 1 FROM job_templates WHERE template_id = ?', (template_id,))
            if not cursor.fetchone():
                return False
            
            # 构建更新语句
            update_fields = []
            params = []
            
            if "name" in template_data:
                update_fields.append("name = ?")
                params.append(template_data["name"])
            
            if "description" in template_data:
                update_fields.append("description = ?")
                params.append(template_data["description"])
            
            if "task_groups" in template_data:
                update_fields.append("task_groups = ?")
                params.append(json.dumps(template_data["task_groups"]))
            
            if "constraints" in template_data:
                update_fields.append("constraints = ?")
                params.append(json.dumps(template_data["constraints"]))
            
            update_fields.append("updated_at = ?")
            params.append(time.time())
            
            # 添加模板ID到参数列表
            params.append(template_id)
            
            # 执行更新
            cursor.execute(f'''
                UPDATE job_templates 
                SET {", ".join(update_fields)}
                WHERE template_id = ?
            ''', params)
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 成功更新作业模板: {template_id}")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 更新作业模板时出错: {e}")
            return False

    def delete_job_template(self, template_id: str) -> bool:
        """删除作业模板"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM job_templates WHERE template_id = ?', (template_id,))
            
            conn.commit()
            conn.close()
            
            print(f"[NodeManager] 成功删除作业模板: {template_id}")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 删除作业模板时出错: {e}")
            return False 

    def clear_all_data(self) -> bool:
        """清空所有数据库表并删除表结构
        
        注意：此方法会删除所有数据，包括：
        - 所有作业
        - 所有节点
        - 所有分配
        - 所有任务状态
        - 所有作业模板
        
        同时也会删除所有表结构，下次启动时会重新创建
        
        Returns:
            bool: 操作是否成功
        """
        try:
            print("\n[NodeManager] 开始清空所有数据和表结构")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 按照依赖关系顺序删除表
            # 1. 先删除任务状态表（依赖于分配）
            cursor.execute('DROP TABLE IF EXISTS task_status')
            print("[NodeManager] 已删除任务状态表")
            
            # 2. 删除分配表（依赖于作业和节点）
            cursor.execute('DROP TABLE IF EXISTS allocations')
            print("[NodeManager] 已删除分配表")
            
            # 3. 删除作业表
            cursor.execute('DROP TABLE IF EXISTS jobs')
            print("[NodeManager] 已删除作业表")
            
            # 4. 删除节点表
            cursor.execute('DROP TABLE IF EXISTS nodes')
            print("[NodeManager] 已删除节点表")
            
            # # 5. 删除作业模板表
            # cursor.execute('DROP TABLE IF EXISTS job_templates')
            # print("[NodeManager] 已删除作业模板表")
            
            conn.commit()
            conn.close()
            
            print("[NodeManager] 所有数据和表结构已清空")
            return True
            
        except Exception as e:
            print(f"[NodeManager] 清空数据和表结构时出错: {e}")
            return False 