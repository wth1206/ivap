<template>
  <div v-if="hasData" ref="chartRef" class="chart" />
  <EmptyState
    v-else
    title="暂无类别数据"
    description="完成一次目标检测后，这里会显示类别分布。"
  />
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import EmptyState from './EmptyState.vue'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Object, default: () => ({}) },
  height: { type: Number, default: 260 },
})

const chartRef = ref(null)
let chart = null

const hasData = computed(() => Object.keys(props.data || {}).length > 0)

function render() {
  if (!hasData.value) {
    chart?.dispose()
    chart = null
    return
  }
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const entries = Object.entries(props.data).sort((a, b) => b[1] - a[1])
  chart.setOption({
    grid: { left: 12, right: 18, top: 24, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category',
      data: entries.map(([name]) => name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#64748b', fontSize: 11, interval: 0 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: entries.map(([, value]) => value),
        barMaxWidth: 30,
        itemStyle: {
          color: '#2563eb',
          borderRadius: [6, 6, 0, 0],
        },
        label: { show: true, position: 'top', color: '#334155', fontSize: 11 },
      },
    ],
  })
  chart.resize()
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', onResize)
})

watch(
  () => props.data,
  () => nextTick(render),
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind('height + "px"');
}
</style>
