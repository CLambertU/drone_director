import { computed, reactive, shallowRef } from 'vue';
import { api, downloadReport } from '../services/api';
import type { Snapshot } from '../types/simulation';

export const snapshot = shallowRef<Snapshot | null>(null);
export const connection = reactive({ state: 'connecting' as 'connecting' | 'live' | 'reconnecting', error: '', busy: false, lastUpdate: 0 });
export const selectedAircraftId = shallowRef('');
export const selectedAircraft = computed(() => snapshot.value?.aircraft.find(a => a.id === selectedAircraftId.value));
let socket: WebSocket | undefined;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let disposed = false;
let attempt = 0;

function accept(data: Snapshot) {
  if (!data?.simulation || !data.metrics) return;
  snapshot.value = { ...data, environment: 'environment' in data ? data.environment : snapshot.value?.environment };
  connection.lastUpdate = Date.now();
}

export async function refresh() {
  const requestedAt = connection.lastUpdate;
  const data = await api<Snapshot>('/simulation/state');
  // A WebSocket snapshot arriving after this request began is fresher than the HTTP read.
  if (connection.lastUpdate === requestedAt) accept(data);
}

function connect() {
  if (disposed) return;
  connection.state = attempt ? 'reconnecting' : 'connecting';
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`);
  socket.onopen = () => { connection.state = 'live'; attempt = 0; };
  socket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'snapshot') accept(message.data);
    } catch { connection.error = '收到无法解析的实时数据，请重新连接。'; }
  };
  socket.onclose = () => {
    if (disposed) return;
    connection.state = 'reconnecting';
    retryTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 10000));
  };
  socket.onerror = () => socket?.close();
}

export function startConnection() {
  disposed = false;
  refresh().catch(error => { connection.error = `后端连接失败：${error.message}`; });
  connect();
}

export function stopConnection() {
  disposed = true;
  clearTimeout(retryTimer);
  socket?.close();
}

export async function command(path: string, body: unknown = {}) {
  if (connection.busy) return;
  connection.busy = true;
  connection.error = '';
  try { await api(path, body); await refresh(); }
  catch (error) { connection.error = error instanceof Error ? error.message : String(error); }
  finally { connection.busy = false; }
}

export async function exportReport() {
  try { await downloadReport(); }
  catch (error) { connection.error = error instanceof Error ? error.message : String(error); }
}
