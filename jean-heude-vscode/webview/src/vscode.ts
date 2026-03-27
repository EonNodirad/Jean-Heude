/**
 * Singleton acquireVsCodeApi() — doit être appelé une seule fois.
 */
declare function acquireVsCodeApi(): {
  postMessage(msg: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _api = (typeof acquireVsCodeApi !== 'undefined') ? acquireVsCodeApi() : null as any;

export function postMessage(msg: unknown): void {
  _api?.postMessage(msg);
}

export function getState<T>(): T | undefined {
  return _api?.getState() as T | undefined;
}

export function setState(state: unknown): void {
  _api?.setState(state);
}
