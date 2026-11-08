import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'
import HomeView from '@/views/HomeView.vue'
import DetectView from '@/views/DetectView.vue'
import AnalysisView from '@/views/AnalysisView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import AgentView from '@/views/AgentView.vue'
import HistoryView from '@/views/HistoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'home', component: HomeView, meta: { title: '系统首页' } },
        { path: 'detect', name: 'detect', component: DetectView, meta: { title: '图像检测' } },
        { path: 'analysis', name: 'analysis', component: AnalysisView, meta: { title: '智能分析' } },
        { path: 'knowledge', name: 'knowledge', component: KnowledgeView, meta: { title: '知识库' } },
        { path: 'agent', name: 'agent', component: AgentView, meta: { title: 'Agent 对话' } },
        { path: 'history', name: 'history', component: HistoryView, meta: { title: '历史任务' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
