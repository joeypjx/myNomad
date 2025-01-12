<template>
  <div class="job-list">
    <!-- 调试信息 -->
    <div class="debug-info">
      <p>Loading: {{ loading }}</p>
      <p>Jobs count: {{ jobs.length }}</p>
    </div>

    <!-- 作业列表 -->
    <div v-for="job in jobs" :key="job.job_id" class="job-card">
      <!-- 作业信息 -->
      <div class="job-header">
        <div class="job-info">
          <span class="job-id">作业 ID: {{ job.job_id }}</span>
          <el-tag :type="getStatusType(job.status)" class="job-status">
            {{ job.status }}
          </el-tag>
          <span class="task-groups">任务组数量: {{ job.task_groups.length }}</span>
        </div>
        <div class="job-actions">
          <el-button
            size="small"
            type="danger"
            :disabled="job.status === 'dead'"
            @click="handleStopJob(job.job_id)"
          >
            停止
          </el-button>
        </div>
      </div>

      <!-- 分配信息表格 -->
      <div v-for="allocation in job.allocations" :key="allocation.allocation_id" class="allocation-section">
        <div class="allocation-header">
          <div class="allocation-info">
            <span class="allocation-id">分配 ID: {{ allocation.allocation_id }}</span>
            <span class="node-id">节点: {{ allocation.node_id }}</span>
            <span class="task-group">任务组: {{ allocation.task_group }}</span>
            <el-tag size="small" :type="getAllocationStatusType(allocation.status)" class="allocation-status">
              {{ allocation.status }}
            </el-tag>
            <span class="duration">运行时间: {{ formatDuration(allocation.start_time, allocation.end_time) }}</span>
          </div>
        </div>

        <!-- 任务信息表格 -->
        <el-table 
          :data="allocation.tasks ? Object.entries(allocation.tasks).map(([name, task]) => ({
            name,
            ...task,
            resources: task.resources || { cpu: 0, memory: 0 },
            config: task.config || {}
          })) : []" 
          style="width: 100%" 
          class="task-table"
        >
          <el-table-column prop="name" label="任务名称" width="180" />
          <el-table-column label="资源" width="200">
            <template #default="{ row }">
              <div>CPU: {{ row.resources?.cpu || 0 }}</div>
              <div>内存: {{ row.resources?.memory || 0 }}MB</div>
            </template>
          </el-table-column>
          <el-table-column label="配置" width="200">
            <template #default="{ row }">
              <div v-if="row.config?.command">命令: {{ row.config.command }}</div>
              <div v-if="row.config?.image">镜像: {{ row.config.image }}</div>
              <div v-if="row.config?.port">端口: {{ row.config.port }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="getTaskStatusType(row.status)">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="运行时间" min-width="200">
            <template #default="{ row }">
              {{ formatDuration(row.start_time, row.end_time) }}
            </template>
          </el-table-column>
          <el-table-column label="退出码" width="100">
            <template #default="{ row }">
              {{ row.exit_code ?? '-' }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useJobStore } from '../stores/jobs'
import type { JobStatus, AllocationStatus } from '../types'

const jobStore = useJobStore()
const { jobs, loading } = storeToRefs(jobStore)
const timer = ref<number>()

// 获取状态对应的类型
function getStatusType(status: JobStatus) {
  const types: Record<string, string> = {
    pending: 'info',
    running: 'success',
    complete: 'success',
    failed: 'danger',
    lost: 'warning',
    dead: 'info',
    degraded: 'warning',
    blocked: 'danger'
  }
  return types[status] || 'info'
}

// 获取分配状态对应的类型
function getAllocationStatusType(status: AllocationStatus) {
  const types: Record<string, string> = {
    pending: 'info',
    running: 'success',
    complete: 'success',
    failed: 'danger',
    lost: 'warning',
    stopped: 'info'
  }
  return types[status] || 'info'
}

// 格式化持续时间
function formatDuration(startTime: number | null, endTime: number | null): string {
  if (!startTime) return '-'
  const end = endTime || Date.now()
  const duration = end - startTime
  const seconds = Math.floor(duration / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}小时 ${minutes % 60}分钟`
  }
  if (minutes > 0) {
    return `${minutes}分钟 ${seconds % 60}秒`
  }
  return `${seconds}秒`
}

// 停止作业
async function handleStopJob(jobId: string) {
  await jobStore.stopJob(jobId)
}

// 获取任务状态对应的类型
function getTaskStatusType(status: string) {
  const types: Record<string, string> = {
    pending: 'info',
    running: 'success',
    complete: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

// 组件挂载时开始定时获取数据
onMounted(() => {
  console.log('组件挂载，开始获取作业列表')
  // 立即获取一次数据
  jobStore.fetchJobs()
  
  // 设置定时器，每5秒刷新一次
  timer.value = window.setInterval(() => {
    console.log('定时刷新作业列表')
    jobStore.fetchJobs()
  }, 5000)
})

// 组件卸载时清除定时器
onUnmounted(() => {
  if (timer.value) {
    console.log('组件卸载，清除定时器')
    clearInterval(timer.value)
  }
})
</script>

<style scoped>
.job-list {
  padding: 20px;
}

.debug-info {
  margin-bottom: 20px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.job-card {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.job-header {
  padding: 15px 20px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.job-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.job-id {
  font-weight: bold;
}

.job-status {
  margin: 0 10px;
}

.allocation-section {
  margin: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.allocation-header {
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.allocation-info {
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.allocation-id {
  font-weight: bold;
}

.task-table {
  margin: 10px;
}
</style> 