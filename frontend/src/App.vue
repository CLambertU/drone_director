<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import CityScene from './components/CityScene.vue';
import ControlPanel from './components/ControlPanel.vue';
import MetricsChart from './components/MetricsChart.vue';
import EventTimeline from './components/EventTimeline.vue';
import { command, connection, selectedAircraftId, snapshot, startConnection, stopConnection } from './stores/simulation';

const scene = ref<InstanceType<typeof CityScene>>();
const tracks = ref(true);
const labels = ref(true);
const connectedLabel = computed(() => ({ connecting: '正在连接', live: '实时同步', reconnecting: '断线重连中' })[connection.state]);
onMounted(startConnection);
onBeforeUnmount(stopConnection);
</script>

<template>
  <div class="console-shell">
    <header class="topbar">
      <div class="brand"><div class="brand-symbol" aria-hidden="true">✳</div><div><h1>天枢智航<span>TIANSHU</span></h1><p>城市低空交通智能规划与自主协同系统</p></div></div>
      <div class="topbar-context"><span class="workspace-tag">城市空中交通规划创新赛</span><span class="connection-status" :class="connection.state"><i />{{ connectedLabel }}</span></div>
    </header>
    <div v-if="connection.error" class="error-banner" role="alert"><span>{{ connection.error }}</span><button aria-label="关闭错误提示" @click="connection.error = ''">×</button></div>
    <main class="workspace">
      <section class="scene-panel" aria-label="城市低空交通监控">
        <div class="scene-heading"><div><span class="eyebrow">LOW-ALTITUDE AIRSPACE</span><h2>{{ snapshot?.environment?.name || '城市低空运行空域' }}<span class="scene-subtitle">三维态势</span></h2></div><div class="map-tools"><label><input v-model="tracks" type="checkbox" />轨迹</label><label><input v-model="labels" type="checkbox" />标注</label><button title="恢复城市总览视角" aria-label="恢复总览视角" @click="scene?.resetCamera()">⌖ 总览</button></div></div>
        <CityScene ref="scene" :state="snapshot" :selected-id="selectedAircraftId" :show-tracks="tracks" :show-labels="labels" @select="selectedAircraftId = $event" />
        <div v-if="!snapshot?.aircraft.length" class="scene-empty"><span class="empty-cross" aria-hidden="true">⌖</span><h3>建立城市低空运行场景</h3><p>由仿真器生成 100 架飞行器与任务，<br />观察航路规划、协同调度和事件处置。</p><button class="primary" :disabled="connection.busy || connection.state !== 'live'" @click="command('/simulation/demo', { aircraft_count: 100, seed: 42 })">{{ connection.busy ? '正在生成场景…' : '创建演示场景' }}</button></div>
        <div v-if="snapshot?.simulation.demo_complete" class="demo-complete">✓ 自动演示完成 · 可查看事件结果与导出报告</div>
        <div class="map-legend"><span><i class="legend-teal" />正常航路 / 飞行器</span><span><i class="legend-amber" />拥堵 / 备降</span><span><i class="legend-red" />管制 / 冲突</span><span class="legend-note">ENU 米制坐标 · 离线仿真城市</span></div>
        <div class="map-help">拖动旋转视角 · 滚轮缩放 · 单击飞行器查看详情</div>
      </section>
      <ControlPanel />
      <section class="analytics-panel">
        <div class="analytics-summary"><div><h2>运行趋势</h2><p>基于实际仿真采样</p></div><div class="summary-stat"><span>累计飞行</span><strong>{{ snapshot ? (snapshot.metrics.total_flight_distance_m / 1000).toFixed(2) : '—' }}<small>km</small></strong></div><div class="summary-stat"><span>应急处理</span><strong>{{ snapshot?.metrics.emergency_response_ms?.toFixed(1) ?? '—' }}<small>ms</small></strong></div><div class="summary-stat"><span>完成任务</span><strong>{{ snapshot?.metrics.completed_missions ?? '—' }}<small>项</small></strong></div></div>
        <MetricsChart :history="snapshot?.history ?? []" />
      </section>
      <section class="events-panel"><div class="panel-heading"><h2>实时事件时间线</h2><span class="small-code">{{ snapshot?.events.length ?? 0 }} 条 · 仿真时间</span></div><EventTimeline :events="snapshot?.events ?? []" /></section>
    </main>
    <footer class="footer"><span>可解释决策：多项加权 A* · 轨迹预测 · 规则解脱</span><span>环境 v{{ snapshot?.environment_version ?? '—' }} · 状态 v{{ snapshot?.version ?? '—' }}<span class="footer-divider">/</span>感知 → 分析 → 决策 → 执行 → 反馈</span></footer>
  </div>
</template>
