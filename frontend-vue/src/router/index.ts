/**
 * Router — 7 kebab-case lazy-loaded pages plus a catch-all NotFound.
 */

import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/providers' },
        {
          path: 'providers',
          name: 'providers',
          component: () => import('@/pages/ProvidersPage.vue'),
        },
        {
          path: 'model-settings',
          name: 'model-settings',
          component: () => import('@/pages/ModelSettingsPage.vue'),
        },
        {
          path: 'config-panel',
          name: 'config-panel',
          component: () => import('@/pages/ConfigPanelPage.vue'),
        },
        {
          path: 'prompt-studio',
          name: 'prompt-studio',
          component: () => import('@/pages/prompt-studio/PromptStudioPage.vue'),
        },
        {
          path: 'debugger',
          name: 'debugger',
          component: () => import('@/pages/debugger/DebuggerPage.vue'),
        },
        {
          path: 'user-options',
          name: 'user-options',
          component: () => import('@/pages/user-options/UserOptionsPage.vue'),
        },
        {
          path: 'appearance',
          name: 'appearance',
          component: () => import('@/pages/AppearanceSettingsPage.vue'),
        },
        {
          path: '/:pathMatch(.*)*',
          name: 'not-found',
          component: () => import('@/pages/NotFoundPage.vue'),
        },
      ],
    },
  ],
})

export default router
