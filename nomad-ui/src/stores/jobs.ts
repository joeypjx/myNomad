import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAllJobs, stopJob, deleteJob, restartJob } from '../api/jobs'
import type { Job } from '../types'

export const useJobStore = defineStore('jobs', () => {
    const jobs = ref<Job[]>([])
    const loading = ref(false)

    // 获取所有作业
    async function fetchJobs() {
        loading.value = true
        try {
            const response = await getAllJobs()
            jobs.value = response.jobs
        } catch (error) {
            console.error('获取作业列表失败:', error)
        } finally {
            loading.value = false
        }
    }

    // 停止作业
    async function stopJobById(jobId: string) {
        try {
            await stopJob(jobId)
            // 立即刷新作业列表
            await fetchJobs()
        } catch (error) {
            console.error('停止作业失败:', error)
            throw error
        }
    }

    // 删除作业
    async function deleteJobById(jobId: string) {
        try {
            console.log('Store: 开始删除作业:', jobId)
            await deleteJob(jobId)
            console.log('Store: 删除作业成功，开始刷新列表')
            // 立即刷新作业列表
            await fetchJobs()
            console.log('Store: 作业列表已刷新')
        } catch (error) {
            console.error('Store: 删除作业失败:', error)
            throw error
        }
    }

    // 重启作业
    async function restartJobById(jobId: string) {
        try {
            await restartJob(jobId)
            // 立即刷新作业列表
            await fetchJobs()
        } catch (error) {
            console.error('重启作业失败:', error)
            throw error
        }
    }

    return {
        jobs,
        loading,
        fetchJobs,
        stopJob: stopJobById,
        deleteJob: deleteJobById,
        restartJob: restartJobById
    }
}) 