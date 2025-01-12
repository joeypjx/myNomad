<template>
  <el-config-provider namespace="ep">
    <div class="app">
      <el-container>
        <el-header>
          <h1>Nomad 作业管理</h1>
        </el-header>
        <el-main>
          <job-list />
        </el-main>
      </el-container>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import JobList from './components/JobList.vue'
</script>

<style>
.app {
  min-height: 100vh;
}

.el-header {
  background-color: #409EFF;
  color: white;
  line-height: 60px;
  text-align: center;
}

.el-main {
  background-color: #f5f7fa;
}
</style>
