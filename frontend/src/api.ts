const messages: Record<string, string> = {
  LOCAL_APPROVAL_REQUIRED: '本机观察授权未建立或已过期。请通过本机启动器重新打开工作台。',
  SAME_ORIGIN_REQUIRED: '请求来源未获授权，请从本机启动器进入。',
  B_TIMEOUT: 'B 服务响应超时。请确认本机服务状态后重试。',
  B_UNAVAILABLE: '暂时无法读取 B 服务。当前没有展示旧运行数据，请重试。',
  B_CONTRACT_MISMATCH: 'B 返回的接口格式不匹配，已停止展示。',
  RUN_NOT_FOUND: '本次运行不存在或不在观察范围内。',
  BATCH_ALREADY_RUNNING: '已有一批随机测试正在运行，请等待当前批次完成。',
  BSCALE_SOURCE_UNAVAILABLE: 'B-SCALE 冻结数据源未配置或不可读取，请检查本机启动配置。',
  BATCH_EXECUTION_FAILED: '随机测试批次执行失败，请查看本机服务日志。',
};

export async function api<T>(path: string, options: { method?: 'GET' | 'POST'; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  try {
    const response = await fetch('/observer/' + path, {
      method: options.method ?? 'GET', credentials: 'same-origin', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-Workbench-Request': '1' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(messages[value.code as string] ?? '读取失败，请检查本机服务后重试。');
    return value as T;
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (controller.signal.aborted) throw new Error('请求超过 8 秒，已取消等待。请重试或导入已保存的回放。');
    if (error instanceof TypeError) throw new Error('连接已断开。请检查本机服务，或导入已保存的证据回放。');
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener('abort', abort);
  }
}

// This is a one-use observer grant, never a B admin/session credential. It is removed
// from browser history before the first request and never saved in browser storage.
export async function pairFromFragment(): Promise<void> {
  const params = new URLSearchParams(location.hash.slice(1));
  const grant = params.get('pair');
  if (grant) {
    params.delete('pair');
    const rest = params.toString();
    history.replaceState(null, '', location.pathname + location.search + (rest ? '#' + rest : ''));
    await api('pair', { method: 'POST', body: { grant } });
  }
}
