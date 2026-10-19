/* API 封装：统一处理 JSON 请求与业务错误 */
const API = (() => {
  async function request(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    let data = null;
    try {
      data = await res.json();
    } catch (err) {
      throw new Error('服务器返回了无法解析的内容');
    }
    if (!res.ok) {
      const error = new Error(data && data.error ? data.error : `请求失败 (${res.status})`);
      error.state = data && data.state;
      throw error;
    }
    return data;
  }

  return {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}) }),
  };
})();
