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
        self.nodes = {}  # 存储节点ID到节点对象的映射
        self.allocations = {}  # 存储分配ID到分配对象的映射
        print("[NodeManager] 节点管理器已初始化")

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
                PRIMARY KEY (allocation_id, task_name),
                FOREIGN KEY(allocation_id) REFERENCES allocations(allocation_id)
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
                            (allocation_id, task_name, status, start_time, end_time, error, exit_code, last_update)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            allocation_id,
                            task_name,
                            task_status["status"],
                            task_status["start_time"],
                            task_status["end_time"],
                            task_status.get("error"),
                            task_status.get("exit_code"),
                            heartbeat_data["timestamp"]
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

    def _check_node_health(self):
        """检查节点健康状态"""
        while True:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timeout_threshold = time.time() - self.heartbeat_timeout
                
                # 标记不健康的节点
                cursor.execute('''
                    UPDATE nodes 
                    SET healthy = 0 
                    WHERE last_heartbeat < ? AND healthy = 1
                ''', (timeout_threshold,))
                
                if cursor.rowcount > 0:
                    print(f"[NodeManager] 标记 {cursor.rowcount} 个节点为不健康状态（心跳超时）")
                    
                    # 获取不健康节点上的分配
                    cursor.execute('''
                        SELECT a.allocation_id, a.job_id, a.node_id
                        FROM allocations a
                        JOIN nodes n ON a.node_id = n.node_id
                        WHERE n.healthy = 0 
                        AND a.status NOT IN ('complete', 'failed', 'lost', 'stopped')
                    ''')
                    lost_allocations = cursor.fetchall()
                    
                    # 更新这些分配的状态为 LOST
                    for alloc in lost_allocations:
                        allocation_id, job_id, node_id = alloc
                        print(f"[NodeManager] 标记分配 {allocation_id} 为丢失状态（节点 {node_id} 不健康）")
                        
                        cursor.execute('''
                            UPDATE allocations 
                            SET status = ?, 
                                end_time = ?
                            WHERE allocation_id = ?
                        ''', ('lost', time.time(), allocation_id))
                        
                        # 更新相关任务的状态
                        cursor.execute('''
                            UPDATE task_status
                            SET status = ?,
                                end_time = ?
                            WHERE allocation_id = ?
                            AND status NOT IN ('complete', 'failed')
                        ''', ('lost', time.time(), allocation_id))
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[NodeManager] 健康检查时出错: {e}")
            
            time.sleep(5)

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
                        SELECT task_name, resources, config, status, start_time, end_time, exit_code
                        FROM task_status
                        WHERE allocation_id = ?
                    """, (allocation_id,))
                    tasks = cursor.fetchall()
                    
                    tasks_info = {}
                    for task in tasks:
                        name, resources, config, task_status, task_start, task_end, exit_code = task
                        tasks_info[name] = {
                            "resources": json.loads(resources) if resources else {},
                            "config": json.loads(config) if config else {},
                            "status": task_status,
                            "start_time": task_start,
                            "end_time": task_end,
                            "exit_code": exit_code
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
                SELECT node_id, region, resources, healthy, last_heartbeat 
                FROM nodes
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            nodes = []
            for row in rows:
                nodes.append({
                    "node_id": row[0],
                    "region": row[1],
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

    def get_allocation_tasks(self, allocation_id: str) -> List[Dict]:
        """获取分配的所有任务状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_name, status, start_time, end_time, error, exit_code
                FROM task_status
                WHERE allocation_id = ?
            ''', (allocation_id,))
            rows = cursor.fetchall()
            conn.close()
            
            tasks = []
            for row in rows:
                tasks.append({
                    "task_name": row[0],
                    "status": row[1],
                    "start_time": row[2],
                    "end_time": row[3],
                    "error": row[4],
                    "exit_code": row[5]
                })
            return tasks
        except Exception as e:
            print(f"[NodeManager] 获取任务状态信息时出错: {e}")
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
        """
        try:
            # 获取作业信息
            job_info = self.get_job_info(job_id)
            if not job_info:
                return False

            # 获取所有健康的节点
            healthy_nodes = [node for node in self.nodes.values() if node.healthy]
            if not healthy_nodes:
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
                for node in healthy_nodes:
                    if (node.available_resources.get("cpu", 0) >= total_cpu and 
                        node.available_resources.get("memory", 0) >= total_memory):
                        resource_satisfied = True
                        break

                if not resource_satisfied:
                    return False

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