/**
 * logParser.js — 日志解析、格式化、退避轮询共享模块
 *
 * 被 LogPanel.svelte 和 LogViewer.svelte 共用，确保两组件的日志
 * 解析行为和轮询策略完全一致。
 */

// ── 轮询常量 ──────────────────────────────────────────────
export const POLL_INTERVAL_BASE = 5000;      // 正常间隔 5s
export const POLL_INTERVAL_MAX = 60000;      // 最大间隔 60s
export const POLL_BACKOFF_MULTIPLIER = 2;    // 退避倍数
export const POLL_ERROR_THRESHOLD = 3;       // 连续错误阈值

// ── 正则 ──────────────────────────────────────────────────
/** ISO 8601 时间戳正则 */
export const TIMESTAMP_REGEX = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)/;

/** 带方括号模块名的日志级别匹配（如 `[module] - INFO -`），用于 bot 日志 */
export const LEVEL_REGEX_BRACKET = /\]\s+-\s+(INFO|WARNING|ERROR|CRITICAL)\s+-\s+/;

/** 通用日志级别匹配（如 ` - INFO - ），用于全局日志 */
export const LEVEL_REGEX_DEFAULT = / - (INFO|WARNING|ERROR|CRITICAL) - /;

// ── 时间戳格式化 ──────────────────────────────────────────
/**
 * 将 UTC 时间戳字符串格式化为用户时区的可读时间。
 * 使用 'sv-SE' locale 技巧获取 YYYY-MM-DD HH:mm:ss 格式。
 *
 * @param {string|null} utcString - ISO 8601 UTC 时间戳
 * @param {string} timeZone - IANA 时区标识符（如 'Asia/Shanghai'）
 * @returns {string} 格式化后的时间字符串
 */
export function formatTimestamp(utcString, timeZone) {
    if (!utcString) return '...';
    try {
        return new Intl.DateTimeFormat('sv-SE', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZone: timeZone
        }).format(new Date(utcString));
    } catch (e) {
        console.error(`Invalid timezone: ${timeZone}`, e);
        // 回退：提取原始 UTC 字符串的前 19 个字符
        return utcString.replace('T', ' ').substring(0, 19);
    }
}

// ── 日志行解析 ────────────────────────────────────────────
/**
 * 将原始日志文本解析为结构化日志条目数组。
 * 自动识别时间戳、日志级别、剥离模块名前缀，仅保留消息正文。
 *
 * @param {string} rawLogs - 原始多行日志文本
 * @param {string} timezone - 用户时区
 * @param {Object} [options] - 解析选项
 * @param {number} [options.limit=1000] - 最大渲染行数
 * @param {RegExp} [options.levelRegex=LEVEL_REGEX_BRACKET] - 日志级别匹配正则
 * @returns {{ parsedLogs: Array, hiddenLogCount: number }}
 */
export function parseLogs(rawLogs, timezone, options = {}) {
    const { limit = 1000, levelRegex = LEVEL_REGEX_BRACKET } = options;
    const allLines = (rawLogs || '').split('\n').filter(line => line.trim() !== '');
    const hiddenLogCount = Math.max(0, allLines.length - limit);
    const visibleLines = hiddenLogCount > 0 ? allLines.slice(-limit) : allLines;

    let parseIdx = 0;
    const parsedLogs = visibleLines.map(line => {
        const tsMatch = line.match(TIMESTAMP_REGEX);
        const lvMatch = line.match(levelRegex);
        const originalTimestamp = tsMatch ? tsMatch[1] : null;
        const level = lvMatch ? lvMatch[1] : 'UNKNOWN';

        let messageText = line;
        // 优先按级别匹配剥离（能同时去掉时间戳和模块名）
        if (lvMatch) {
            messageText = line.substring(lvMatch.index + lvMatch[0].length);
        } else if (tsMatch) {
            // 回退：仅剥离时间戳
            messageText = line.substring(tsMatch[0].length).trim();
        }

        return {
            level,
            message: messageText,
            _uid: parseIdx++,
            originalLine: line,
            formattedTimestamp: originalTimestamp
                ? formatTimestamp(originalTimestamp, timezone)
                : '...'
        };
    });

    return { parsedLogs, hiddenLogCount };
}

/** @deprecated 请使用 parseLogs */
export const parseLogLines = parseLogs;

// ── 退避轮询管理器 ────────────────────────────────────────
/**
 * 带退避策略的轮询管理器。
 *
 * 行为：
 * - 立即执行首次拉取，之后按间隔定时轮询
 * - 连续成功：间隔重置为 POLL_INTERVAL_BASE
 * - 连续失败 ≥ POLL_ERROR_THRESHOLD：间隔翻倍（上限 POLL_INTERVAL_MAX）
 * - 调用 stop() 清理定时器
 *
 * @example
 *   const poller = new LogPoller(async () => {
 *       const text = await fetchLogs();
 *       rawLogs.set(text);
 *   });
 *   poller.start();  // onMount
 *   poller.stop();   // onDestroy
 */
export class LogPoller {
    /**
     * @param {Function} fetchFn - 异步拉取函数，成功返回无值，失败抛异常
     * @param {{ onError?: Function }} [callbacks]
     */
    constructor(fetchFn, { onError } = {}) {
        this._fetchFn = fetchFn;
        this._onError = onError;
        this._timer = null;
        this._consecutiveErrors = 0;
        this._currentInterval = POLL_INTERVAL_BASE;
    }

    /** 启动轮询（立即拉取一次 + 定时） */
    start() {
        this._execute();
    }

    /** 停止轮询，清理定时器 */
    stop() {
        if (this._timer !== null) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }

    /** @private 执行单次拉取并调度下一次 */
    async _execute() {
        if (!this._fetchFn) return;
        try {
            await this._fetchFn();
            // 成功 — 重置退避
            this._consecutiveErrors = 0;
            this._currentInterval = POLL_INTERVAL_BASE;
        } catch (e) {
            this._consecutiveErrors++;
            this._onError?.(e, this._consecutiveErrors);
            // 连续失败超过阈值，启动退避
            if (this._consecutiveErrors >= POLL_ERROR_THRESHOLD) {
                this._currentInterval = Math.min(
                    this._currentInterval * POLL_BACKOFF_MULTIPLIER,
                    POLL_INTERVAL_MAX
                );
            }
        }
        this._scheduleNext();
    }

    /** @private 重新调度定时器 */
    _scheduleNext() {
        this.stop();
        this._timer = setInterval(() => this._execute(), this._currentInterval);
    }
}
