<template>
  <div class="job-list">
    <!-- 顶部操作栏 -->
    <div class="top-actions">
      <el-button type="success" @click="showSaveTemplateDialog()">保存作业模板</el-button>
      <el-button type="primary" @click="showSubmitDialog()">提交新作业</el-button>
    </div>

    <!-- 加载状态 -->
    <el-loading v-if="loading" :fullscreen="true" text="加载中..." />

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
          <el-button
            size="small"
            type="success"
            :disabled="job.status !== 'dead'"
            @click="handleRestartJob(job.job_id)"
          >
            重启
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="showSubmitDialog(job)"
          >
            更新
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            @click="handleDeleteJob(job.job_id)"
          >
            删除
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

    <!-- 删除确认对话框 -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="警告"
      width="30%"
      :close-on-click-modal="false"
    >
      <span>此操作将永久删除该作业及其所有相关资源，是否继续？</span>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="deleteDialogVisible = false">取消</el-button>
          <el-button type="danger" @click="confirmDelete">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 提交作业对话框 -->
    <el-dialog
      v-model="submitDialogVisible"
      :title="isUpdate ? '更新作业' : '提交新作业'"
      width="80%"
      :close-on-click-modal="false"
      :modal="true"
      :lock-scroll="true"
      :show-close="true"
      :center="false"
      :fullscreen="false"
      class="submit-dialog"
      top="5vh"
    >
      <div class="submit-form">
        <el-form style="width: 100%">
          <el-form-item v-if="isUpdate" label="作业ID" class="form-item">
            <el-input v-model="jobId" disabled />
          </el-form-item>
          <el-form-item label="作业配置" class="form-item">
            <el-input
              v-model="jobConfig"
              type="textarea"
              :rows="20"
              :autosize="{ minRows: 20, maxRows: 30 }"
              placeholder="请输入JSON格式的作业配置"
              class="config-textarea"
            />
          </el-form-item>
        </el-form>

        <!-- 模板列表 -->
        <div v-if="!isUpdate" class="template-list">
          <h3>选择作业模板</h3>
          <el-table :data="templates" style="width: 100%" @row-click="handleTemplateSelect">
            <el-table-column prop="name" label="模板名称" width="180" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="primary" link @click.stop="handleTemplateSelect(row)">
                  选择
                </el-button>
                <el-button type="danger" link @click.stop="handleDeleteTemplate(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="submitDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmitJob">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 保存模板对话框 -->
    <el-dialog
      v-model="saveTemplateDialogVisible"
      title="保存作业模板"
      width="80%"
      :close-on-click-modal="false"
      :modal="true"
      :lock-scroll="true"
      :show-close="true"
      :center="false"
      :fullscreen="false"
      class="template-dialog"
      top="5vh"
    >
      <div class="template-form">
        <el-form :model="templateForm" label-width="120px">
          <el-form-item label="模板名称" required>
            <el-input v-model="templateForm.name" placeholder="请输入模板名称" />
          </el-form-item>
          <el-form-item label="模板描述">
            <el-input
              v-model="templateForm.description"
              type="textarea"
              :rows="3"
              placeholder="请输入模板描述"
            />
          </el-form-item>
          <el-form-item label="作业配置" required>
            <el-input
              v-model="templateForm.task_groups"
              type="textarea"
              :rows="20"
              :autosize="{ minRows: 20, maxRows: 30 }"
              placeholder="请输入JSON格式的作业配置"
              class="config-textarea"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="saveTemplateDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSaveTemplate">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useJobStore } from '../stores/jobs'
import type { JobStatus, AllocationStatus } from '../types'
import { ElMessage, ElMessageBox } from 'element-plus'
import 'element-plus/dist/index.css'

const jobStore = useJobStore()
const { jobs, loading } = storeToRefs(jobStore)
const timer = ref<number>()
const deleteDialogVisible = ref(false)
const jobToDelete = ref<string | null>(null)

// 提交作业相关的响应式变量
const submitDialogVisible = ref(false)
const isUpdate = ref(false)
const jobId = ref('')
const jobConfig = ref('')

// 保存模板相关的响应式变量
const saveTemplateDialogVisible = ref(false)
const templateForm = ref({
  name: '',
  description: '',
  task_groups: ''
})

// 模板列表相关的响应式变量
const templates = ref([])

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
  
  // 将时间戳转换为毫秒
  const start = startTime * 1000  // 假设输入是秒级时间戳
  const end = endTime ? endTime * 1000 : Date.now()
  const duration = end - start
  
  // 如果持续时间为负数，返回 '-'
  if (duration < 0) return '-'
  
  const seconds = Math.floor(duration / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (days > 0) {
    return `${days}天 ${hours % 24}小时`
  }
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

// 删除作业
async function handleDeleteJob(jobId: string) {
  jobToDelete.value = jobId
  deleteDialogVisible.value = true
}

// 确认删除
async function confirmDelete() {
  try {
    if (!jobToDelete.value) return
    
    console.log('用户确认删除，开始调用删除接口')
    await jobStore.deleteJob(jobToDelete.value)
    console.log('删除接口调用成功')
    ElMessage.success('作业删除成功')
    deleteDialogVisible.value = false
  } catch (error) {
    console.error('删除作业时出错:', error)
    ElMessage.error('删除作业失败')
  }
}

// 重启作业
async function handleRestartJob(jobId: string) {
  try {
    console.log('开始重启作业:', jobId)
    await jobStore.restartJob(jobId)
    ElMessage.success('作业重启成功')
  } catch (error) {
    console.error('重启作业失败:', error)
    ElMessage.error('重启作业失败')
  }
}

// 获取模板列表
async function fetchTemplates() {
  try {
    const response = await fetch('http://localhost:8500/templates')
    if (!response.ok) {
      throw new Error('获取模板列表失败')
    }
    const data = await response.json()
    templates.value = data.templates
  } catch (error) {
    console.error('获取模板列表时出错:', error)
    ElMessage.error('获取模板列表失败')
  }
}

// 格式化日期
function formatDate(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 处理模板选择
async function handleTemplateSelect(template: any) {
  try {
    // 获取模板详情
    const response = await fetch(`http://localhost:8500/templates/${template.template_id}`)
    if (!response.ok) {
      throw new Error('获取模板详情失败')
    }
    const templateDetail = await response.json()
    
    // 构造作业配置
    const config = {
      task_groups: templateDetail.task_groups,
      constraints: templateDetail.constraints
    }
    
    // 更新作业配置
    jobConfig.value = JSON.stringify(config, null, 2)
    ElMessage.success('已加载模板配置')
  } catch (error) {
    console.error('加载模板配置时出错:', error)
    ElMessage.error('加载模板配置失败')
  }
}

// 显示提交对话框
function showSubmitDialog(job?: any) {
  isUpdate.value = !!job
  if (job) {
    jobId.value = job.job_id
    // 构造作业配置
    const config = {
      task_groups: job.task_groups,
      constraints: job.constraints
    }
    jobConfig.value = JSON.stringify(config, null, 2)
  } else {
    jobId.value = ''
    jobConfig.value = JSON.stringify({
      task_groups: [
        {
          name: "example_group",
          tasks: [
            {
              name: "example_task",
              resources: {
                cpu: 100,
                memory: 128
              },
              config: {
                image: "nginx:latest",
                port: 80
              }
            }
          ]
        }
      ],
      constraints: {
        region: "us-west"
      }
    }, null, 2)
    // 获取模板列表
    fetchTemplates()
  }
  submitDialogVisible.value = true
}

// 处理作业提交
async function handleSubmitJob() {
  try {
    let config
    try {
      config = JSON.parse(jobConfig.value)
    } catch (e) {
      ElMessage.error('JSON格式错误，请检查配置')
      return
    }
    
    if (isUpdate.value) {
      await jobStore.updateJob(jobId.value, config)
      ElMessage.success('作业更新成功')
    } else {
      await jobStore.submitJob(config)
      ElMessage.success('作业提交成功')
    }
    submitDialogVisible.value = false
  } catch (error) {
    console.error('提交作业失败:', error)
    ElMessage.error(isUpdate.value ? '更新作业失败' : '提交作业失败')
  }
}

// 显示保存模板对话框
function showSaveTemplateDialog() {
  // 重置表单
  templateForm.value = {
    name: '',
    description: '',
    task_groups: JSON.stringify({
      task_groups: [
        {
          name: "example_group",
          tasks: [
            {
              name: "example_task",
              resources: {
                cpu: 100,
                memory: 128
              },
              config: {
                image: "nginx:latest",
                port: 80
              }
            }
          ]
        }
      ],
      constraints: {
        region: "us-west"
      }
    }, null, 2)
  }
  saveTemplateDialogVisible.value = true
}

// 处理保存模板
async function handleSaveTemplate() {
  try {
    // 验证必填字段
    if (!templateForm.value.name) {
      ElMessage.error('请输入模板名称')
      return
    }

    // 解析JSON配置
    let taskGroups
    try {
      taskGroups = JSON.parse(templateForm.value.task_groups)
    } catch (e) {
      ElMessage.error('作业配置JSON格式错误')
      return
    }

    // 构造模板数据
    const templateData = {
      name: templateForm.value.name,
      description: templateForm.value.description,
      task_groups: taskGroups.task_groups,
      constraints: taskGroups.constraints
    }

    // 调用后端API保存模板
    const response = await fetch('http://localhost:8500/templates', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(templateData)
    })

    if (!response.ok) {
      throw new Error('保存模板失败')
    }

    const result = await response.json()
    ElMessage.success('模板保存成功')
    saveTemplateDialogVisible.value = false
  } catch (error) {
    console.error('保存模板时出错:', error)
    ElMessage.error('保存模板失败')
  }
}

// 处理删除模板
async function handleDeleteTemplate(template: any) {
  try {
    // 显示确认对话框
    await ElMessageBox.confirm(
      `确定要删除模板 "${template.name}" 吗？`,
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 调用删除API
    const response = await fetch(`http://localhost:8500/templates/${template.template_id}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error('删除模板失败')
    }
    
    // 删除成功后刷新列表
    await fetchTemplates()
    ElMessage.success('模板删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模板时出错:', error)
      ElMessage.error('删除模板失败')
    }
  }
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

.top-actions {
  margin-bottom: 20px;
  display: flex;
  justify-content: flex-end;
}

.submit-form {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.form-item {
  width: 100%;
  margin-bottom: 20px;
}

.form-item :deep(.el-form-item__content) {
  width: 100%;
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

.job-actions {
  display: flex;
  gap: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

:deep(.ep-dialog) {
  margin-top: 8vh !important;
  position: fixed !important;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  margin: 0 !important;
  max-width: 1200px;
  width: 80% !important;
  background-color: white;
}

:deep(.ep-dialog__body) {
  max-height: 70vh;
  overflow-y: auto;
  padding: 20px;
  flex: 1;
  width: 100%;
  box-sizing: border-box;
}

:deep(.ep-dialog__header) {
  padding: 20px;
  margin: 0;
  border-bottom: 1px solid #dcdfe6;
}

:deep(.ep-dialog__footer) {
  padding: 20px;
  margin: 0;
  border-top: 1px solid #dcdfe6;
}

:deep(.ep-overlay) {
  background-color: rgba(0, 0, 0, 0.5);
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  overflow: auto;
  margin: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.config-textarea) {
  width: 100%;
  font-family: monospace;
}

:deep(.config-textarea .el-textarea__inner) {
  width: 100%;
  font-family: monospace;
  min-height: 400px !important;
}

.template-form {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.template-form :deep(.el-form-item__content) {
  width: 100%;
}

.template-form :deep(.el-input),
.template-form :deep(.el-textarea) {
  width: 100%;
}

.template-form :deep(.config-textarea .el-textarea__inner) {
  font-family: monospace;
  min-height: 400px !important;
}

.template-list {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.template-list h3 {
  margin-bottom: 15px;
  color: #303133;
  font-size: 16px;
}

.template-list :deep(.el-table) {
  margin-top: 10px;
}

.template-list :deep(.el-table__row) {
  cursor: pointer;
}

.template-list :deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}
</style> 