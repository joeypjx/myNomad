import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Job } from '../types'
import { jobsApi } from '../api/jobs'

export const useJobStore = defineStore('jobs', () => {
    const jobs = ref<Job[]>([])
    const loading = ref(false)
    const error = ref<string | null>(null)

    // 获取所有作业
    async function fetchJobs() {
        console.log('Store: 开始获取作业列表...')
        loading.value = true
        error.value = null
        try {
            const jobList = await jobsApi.getAllJobs()
            console.log('Store: 获取到作业列表:', jobList)
            jobs.value = jobList
            console.log('Store: jobs 状态更新为:', jobs.value)
        } catch (e) {
            error.value = e instanceof Error ? e.message : '获取作业列表失败'
            console.error('Store: 获取作业列表失败:', e)
        } finally {
            loading.value = false
            console.log('Store: loading 状态更新为:', loading.value)
        }
    }

    // 停止作业
    async function stopJob(jobId: string) {
        console.log(`Store: 开始停止作业 ${jobId}...`)
        try {
            await jobsApi.stopJob(jobId)
            console.log('Store: 作业停止成功，开始刷新作业列表')
            await fetchJobs() // 重新获取作业列表
        } catch (e) {
            error.value = e instanceof Error ? e.message : '停止作业失败'
            console.error('Store: 停止作业失败:', e)
        }
    }

    return {
        jobs,
        loading,
        error,
        fetchJobs,
        stopJob
    }
}) 