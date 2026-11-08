<template>
  <el-tag :type="type" effect="light" size="small">{{ text }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { statusText, statusType } from '@/utils/format'

const props = defineProps({
  status: { type: String, default: '' },
})

const text = computed(() => statusText(props.status))
const type = computed(() => statusType(props.status))
</script>
