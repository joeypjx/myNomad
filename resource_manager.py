from typing import Dict, List, Optional
import time
import threading
import sqlite3
from node_manager import NodeManager
from models import JobStatus
from alarm_manager import AlarmManager

class ResourceManager:
    """资源管理器，负责处理节点心跳和资源监控"""
    
    def __init__(self, node_manager: NodeManager, heartbeat_timeout: int = 15):
        self.node_manager = node_manager
        self.heartbeat_timeout = heartbeat_timeout
        self.is_running = False
        self.check_thread = None
        self.alarm_manager = AlarmManager()
                
        # 启动健康监控线程
        self.start_health_monitor()
    
    def start_health_monitor(self):
        """启动健康监控线程"""
        if not self.is_running:
            self.is_running = True
            self.check_thread = threading.Thread(target=self._check_node_health, daemon=True)
            self.check_thread.start()
            print("[ResourceManager] 节点健康监控已启动")
    
    def stop_health_monitor(self):
        """停止健康监控线程"""
        self.is_running = False
        if self.check_thread:
            print("[ResourceManager] 节点健康监控已停止")
    
    def _check_node_health(self):
        """检查节点健康状态"""
        while self.is_running:
            try:
                conn = sqlite3.connect(self.node_manager.db_path)
                cursor = conn.cursor()
                
                timeout_threshold = time.time() - self.heartbeat_timeout
                
                # 添加更多日志，显示当前状态
                cursor.execute('SELECT COUNT(*) FROM nodes')
                total_nodes = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM nodes WHERE healthy = 0')
                unhealthy_nodes = cursor.fetchone()[0]
                print(f"[ResourceManager] 当前节点状态: 总计 {total_nodes} 个节点, 不健康 {unhealthy_nodes} 个")
                
                # 标记不健康的节点
                cursor.execute('''
                    UPDATE nodes 
                    SET healthy = 0 
                    WHERE last_heartbeat < ? AND healthy = 1
                ''', (timeout_threshold,))
                
                if cursor.rowcount > 0:
                    print(f"[ResourceManager] 标记 {cursor.rowcount} 个节点为不健康状态（心跳超时）")
                    
                    # 获取不健康节点上的分配
                    cursor.execute('''
                        SELECT a.allocation_id, a.job_id, a.node_id
                        FROM allocations a
                        JOIN nodes n ON a.node_id = n.node_id
                        WHERE n.healthy = 0 
                        AND a.status NOT IN ('complete', 'failed', 'lost', 'stopped')
                    ''')
                    lost_allocations = cursor.fetchall()
                    
                    # 收集需要更新状态的作业ID
                    affected_job_ids = set()
                    
                    # 更新这些分配的状态为 LOST
                    for alloc in lost_allocations:
                        allocation_id, job_id, node_id = alloc
                        print(f"[ResourceManager] 标记分配 {allocation_id} 为丢失状态（节点 {node_id} 不健康）")
                        
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
                        
                        # 添加到受影响的作业集合
                        affected_job_ids.add(job_id)
                    
                    # 更新受影响作业的状态
                    for job_id in affected_job_ids:
                        print(f"[ResourceManager] 更新受影响作业 {job_id} 的状态")
                        
                        # 获取作业所有分配的状态统计
                        cursor.execute('''
                            SELECT status, COUNT(*) 
                            FROM allocations 
                            WHERE job_id = ? 
                            GROUP BY status
                        ''', (job_id,))
                        status_counts = dict(cursor.fetchall())
                        
                        # 计算总分配数
                        total_allocations = sum(status_counts.values())
                        
                        # 根据分配状态确定作业状态
                        new_job_status = None
                        
                        # 全部丢失
                        if status_counts.get('lost', 0) == total_allocations:
                            new_job_status = 'lost'
                        # 有运行的但也有丢失的 -> 降级状态
                        elif status_counts.get('running', 0) > 0 and status_counts.get('lost', 0) > 0:
                            new_job_status = 'degraded'
                        # 其他情况，需要更全面的评估
                        elif status_counts.get('lost', 0) > 0:
                            # 如果有丢失的分配，但没有其他运行的分配，可能需要标记为blocked或failed
                            if status_counts.get('failed', 0) > 0:
                                new_job_status = 'failed'
                            else:
                                new_job_status = 'blocked'
                        
                        # 更新作业状态
                        if new_job_status:
                            cursor.execute('''
                                UPDATE jobs 
                                SET status = ? 
                                WHERE job_id = ?
                            ''', (new_job_status, job_id))
                            print(f"[ResourceManager] 作业 {job_id} 状态已更新为: {new_job_status}")
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[ResourceManager] 健康检查时出错: {e}")
            
            time.sleep(5)
    
    def handle_heartbeat(self, heartbeat_data: Dict) -> bool:
        """处理节点心跳数据
        
        Args:
            heartbeat_data: 心跳数据，包含节点ID、资源使用情况等信息
            
        Returns:
            bool: 处理是否成功
        """
        try:
            print(f"\n[ResourceManager] 收到节点 {heartbeat_data['node_id']} 的心跳")
            
            # 检查资源使用情况
            if "resources" in heartbeat_data:
                self.alarm_manager.handle_heartbeat(heartbeat_data["node_id"], heartbeat_data["resources"])
            
            # 调用node_manager存储心跳数据
            success = self.node_manager.update_heartbeat(heartbeat_data)
            if success:
                print(f"[ResourceManager] 节点 {heartbeat_data['node_id']} 心跳处理成功")
            else:
                print(f"[ResourceManager] 节点 {heartbeat_data['node_id']} 心跳处理失败")
            
            return success
            
        except Exception as e:
            print(f"[ResourceManager] 处理心跳时出错: {e}")
            return False
    