<script setup lang="ts">
import { computed } from 'vue';
import { eventLabels, formatTime, type SimulationEvent } from '../types/simulation';
const props = defineProps<{ events: SimulationEvent[] }>();
const newest = computed(() => [...props.events].reverse());
</script>

<template>
  <div class="timeline" aria-label="实时事件时间线">
    <div v-if="!newest.length" class="quiet-state">尚无事件。启动仿真后，决策与处置结果将在此留痕。</div>
    <details v-for="event in newest" :key="event.id" class="event-row" :class="event.severity">
      <summary>
        <span class="event-dot" /><time>{{ formatTime(event.simulation_time) }}</time>
        <span class="event-type">{{ eventLabels[event.type] || event.type }}</span>
        <span class="event-description">{{ event.description || event.id }}</span>
        <span class="event-outcome">{{ event.handled ? '已处理' : '待处理' }}</span>
      </summary>
      <div class="event-detail"><span>处理耗时 {{ event.processing_ms?.toFixed(2) ?? '—' }} ms · {{ event.id }}</span><pre>{{ JSON.stringify(event.result, null, 2) }}</pre></div>
    </details>
  </div>
</template>
