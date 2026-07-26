/**
 * 轻量级前端监控模块
 *
 * 错误上报：捕获未处理 JS 异常和未处理的 Promise rejection
 * 性能指标：预留 web-vitals 接入点（可选依赖）
 *
 * ### 接入 Sentry 示例
 * 1. 安装依赖: npm install @sentry/browser @sentry/vite-plugin
 * 2. 在 vite.config.js 中配置 Sentry 插件
 * 3. 在 initErrorMonitoring 中替换 console.error 为 Sentry.captureException
 *
 * ### 接入 web-vitals 示例
 * 1. 安装依赖: npm install web-vitals
 * 2. 解除下方注释并注册 onLCP / onCLS / onINP 回调
 * 3. 可将指标上报至自建服务或第三方分析平台
 */

/**
 * 初始化错误监控
 *
 * 捕获 window.onerror（未捕获的 JS 异常）和
 * window.onunhandledrejection（未处理的 Promise rejection）。
 * 默认仅 console.error 输出，接入 Sentry 等服务时替换日志逻辑。
 */
export function initErrorMonitoring() {
  if (typeof window === 'undefined') return;

  window.addEventListener('error', (event) => {
    console.error('[Monitor] Uncaught error:', event.error?.message);
    // TODO: 接入 Sentry 或其他上报服务时替换 console.error
    // Sentry.captureException(event.error);
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Monitor] Unhandled rejection:', event.reason?.message);
    // TODO: 接入 Sentry 或其他上报服务时替换 console.error
    // Sentry.captureException(event.reason);
  });
}

/**
 * 初始化性能监控
 *
 * 预留 web-vitals 库接入点。当用户安装 web-vitals 依赖后，
 * 可解除下方注释注册核心 Web 指标回调。
 *
 * 使用示例：
 * ```js
 * import { onLCP, onCLS, onINP } from 'web-vitals';
 *
 * onLCP((metric) => {
 *   console.log('[Monitor] LCP:', metric.value);
 *   // 上报至分析服务
 * });
 *
 * onCLS((metric) => {
 *   console.log('[Monitor] CLS:', metric.value);
 * });
 *
 * onINP((metric) => {
 *   console.log('[Monitor] INP:', metric.value);
 * });
 * ```
 */
export function initPerformanceMonitoring() {
  if (typeof window === 'undefined') return;

  // 预留 web-vitals 接入点
  // import { onLCP, onCLS, onINP } from 'web-vitals';
  // onLCP(console.log); onCLS(console.log); onINP(console.log);
}
