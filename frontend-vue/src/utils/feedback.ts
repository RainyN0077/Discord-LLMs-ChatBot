/**
 * Feedback bridge — module-level holders for naive-ui message/dialog APIs.
 *
 * `useMessage()` / `useDialog()` are inject-based and can only be called
 * inside a component setup that is a child of the corresponding provider.
 * Pinia store actions run outside setup, so the APIs captured by
 * `FeedbackBinder.vue` (mounted inside the providers in App.vue) are exposed
 * here for store-level feedback.
 */

import type { MessageApi } from 'naive-ui'
import type { DialogApiInjection } from 'naive-ui/es/dialog/src/DialogProvider'

let messageApi: MessageApi | null = null
let dialogApi: DialogApiInjection | null = null

export function bindFeedbackApis(
  message: MessageApi | null,
  dialog: DialogApiInjection | null,
): void {
  messageApi = message
  dialogApi = dialog
}

export function getMessageApi(): MessageApi | null {
  return messageApi
}

export function getDialogApi(): DialogApiInjection | null {
  return dialogApi
}
