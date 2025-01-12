import axios from 'axios'
import type { Job } from '../types'

const API_BASE_URL = 'http://localhost:8500'

// 获取所有作业
export async function getAllJobs() {
    console.log('开始获取作业列表...')
    const response = await axios.get<{jobs: Job[], count: number}>(`${API_BASE_URL}/jobs`)
    console.log('API 返回数据:', response.data)
    return response.data
}

// 获取单个作业详情
export async function getJobInfo(jobId: string) {
    console.log(`开始获取作业 ${jobId} 的详情...`)
    const response = await axios.get<Job>(`${API_BASE_URL}/jobs/${jobId}`)
    console.log('作业详情:', response.data)
    return response.data
}

// 停止作业
export async function stopJob(jobId: string) {
    console.log(`开始停止作业 ${jobId}...`)
    const response = await axios.delete(`${API_BASE_URL}/jobs/${jobId}`)
    console.log('停止作业结果:', response.data)
    return response.data
}

// 删除作业
export async function deleteJob(jobId: string) {
    try {
        console.log(`API: 开始删除作业 ${jobId}...`)
        const response = await axios.post<{message: string}>(`${API_BASE_URL}/jobs/${jobId}/delete`)
        console.log('API: 删除作业响应:', response.data)
        return response.data
    } catch (error) {
        console.error('API: 删除作业请求失败:', error)
        throw error
    }
} 