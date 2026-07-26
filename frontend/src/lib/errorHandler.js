// frontend/src/lib/errorHandler.js
// 统一错误处理 — 不引入新库，纯函数实现

export const ErrorLevel = {
    WARN: 'warn',
    ERROR: 'error',
    SILENT: 'silent'
};

export function handleError(context, error, level = ErrorLevel.ERROR) {
    const message = `[${context}] ${error?.message || error}`;
    
    // 开发环境输出到控制台
    if (import.meta?.env?.DEV || location.hostname === 'localhost') {
        console[level === ErrorLevel.WARN ? 'warn' : 'error'](message);
    }
    
    // 生产环境可扩展：发送到日志服务
    // if (level === ErrorLevel.ERROR) { sendToLogService(message); }
    
    return message; // 返回格式化消息供UI显示
}

export function withErrorHandling(fn, context, level) {
    return async (...args) => {
        try {
            return await fn(...args);
        } catch (e) {
            handleError(context, e, level);
            throw e; // 保持原有错误传播
        }
    };
}
