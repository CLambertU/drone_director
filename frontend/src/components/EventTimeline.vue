<script setup lang="ts">
import { computed } from 'vue';
import { eventLabels, formatTime, type SimulationEvent } from '../types/simulation';
const props = defineProps<{ events: SimulationEvent[] }>();
const newest = computed(() => [...props.events].reverse());
function outcome(event: SimulationEvent): string {
  const evacuating = event.result.evacuating_aircraft;
  if (Array.isArray(evacuating) && evacuating.length) return `撤离 ${evacuating.length} 架 · 已处理`;
  return event.handled ? '已处理' : '待处理';
}
</script>

<template>
  <div class="timeline" aria-label="实时事件时间线">
    <div v-if="!newest.length" class="quiet-state">尚无事件。启动仿真后，决策与处置结果将在此留痕。</div>
    <details v-for="event in newest" :key="event.id" class="event-row" :class="event.severity">
      <summary>
        <span class="event-dot" /><time>{{ formatTime(event.simulation_time) }}</time>
        <span class="event-type">{{ eventLabels[event.type] || event.type }}</span>
        <span class="event-description">{{ event.description || event.id }}</span>
        <span class="event-outcome">{{ outcome(event) }}</span>
      </summary>
      <div class="event-detail"><span>处理耗时 {{ event.processing_ms?.toFixed(2) ?? '—' }} ms · {{ event.id }}</span><details class="event-raw"><summary>查看原始处理数据</summary><pre>{{ JSON.stringify(event.result, null, 2) }}</pre></details></div>
    </details>
  </div>
</template>
