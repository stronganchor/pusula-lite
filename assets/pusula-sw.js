const PUSULA_SHELL_CACHE = 'pusula-lite-shell-v1';
const PUSULA_OFFLINE_DB = 'pusula-lite-offline';
const PUSULA_OFFLINE_STORE = 'kv';
const PUSULA_CONFIG_KEY = 'sw-config';

function normalizeUrl(input) {
  try {
    const url = new URL(input, self.location.origin);
    url.hash = '';
    return url.toString();
  } catch (error) {
    return '';
  }
}

function openOfflineDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PUSULA_OFFLINE_DB, 1);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(PUSULA_OFFLINE_STORE)) {
        db.createObjectStore(PUSULA_OFFLINE_STORE, { keyPath: 'key' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IndexedDB acilamadi.'));
  });
}

function offlineStoreGet(key) {
  return openOfflineDb().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(PUSULA_OFFLINE_STORE, 'readonly');
    const store = tx.objectStore(PUSULA_OFFLINE_STORE);
    const request = store.get(key);

    request.onsuccess = () => resolve(request.result ? request.result.value : null);
    request.onerror = () => reject(request.error || new Error('Kayit okunamadi.'));
    tx.oncomplete = () => db.close();
    tx.onerror = () => reject(tx.error || new Error('Islem tamamlanamadi.'));
  }));
}

function offlineStoreSet(key, value) {
  return openOfflineDb().then((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(PUSULA_OFFLINE_STORE, 'readwrite');
    tx.objectStore(PUSULA_OFFLINE_STORE).put({ key, value });
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error || new Error('Kayit yazilamadi.'));
  }));
}

function deleteOfflineDb() {
  return new Promise((resolve) => {
    try {
      const request = indexedDB.deleteDatabase(PUSULA_OFFLINE_DB);
      request.onsuccess = () => resolve();
      request.onerror = () => resolve();
      request.onblocked = () => resolve();
    } catch (error) {
      resolve();
    }
  });
}

async function readConfig() {
  try {
    return await offlineStoreGet(PUSULA_CONFIG_KEY);
  } catch (error) {
    return null;
  }
}

async function writeConfig(config) {
  if (!config || !config.shellUrl) {
    return;
  }

  const shellUrl = normalizeUrl(config.shellUrl);
  const assetUrls = Array.isArray(config.assetUrls)
    ? Array.from(new Set(config.assetUrls.map(normalizeUrl).filter(Boolean)))
    : [];

  await offlineStoreSet(PUSULA_CONFIG_KEY, {
    shellUrl,
    assetUrls,
    updatedAt: Date.now(),
  });
}

async function cacheUrl(url) {
  const normalized = normalizeUrl(url);
  if (!normalized) {
    return;
  }

  try {
    const request = new Request(normalized, {
      credentials: 'same-origin',
      cache: 'no-cache',
    });
    const response = await fetch(request);
    if (!response || !response.ok) {
      return;
    }
    const cache = await caches.open(PUSULA_SHELL_CACHE);
    await cache.put(normalized, response.clone());
  } catch (error) {
    // Best-effort cache update only.
  }
}

async function configureOfflineShell(data) {
  if (!data || !data.shellUrl) {
    return;
  }

  await writeConfig(data);

  const urls = [data.shellUrl].concat(Array.isArray(data.assetUrls) ? data.assetUrls : []);
  await Promise.all(urls.map((url) => cacheUrl(url)));
}

async function purgeOfflineData() {
  try {
    await caches.delete(PUSULA_SHELL_CACHE);
  } catch (error) {
    // Ignore cache cleanup failures.
  }

  await deleteOfflineDb();
}

async function handleLogout(request) {
  try {
    return await fetch(request);
  } finally {
    await purgeOfflineData();
  }
}

async function handleShellNavigation(request, config) {
  const shellUrl = normalizeUrl(config && config.shellUrl);
  const cache = await caches.open(PUSULA_SHELL_CACHE);

  try {
    const response = await fetch(request);
    if (response && response.ok && shellUrl) {
      await cache.put(shellUrl, response.clone());
    }
    return response;
  } catch (error) {
    if (shellUrl) {
      const cached = await cache.match(shellUrl);
      if (cached) {
        return cached;
      }
    }

    const fallback = await cache.match(normalizeUrl(request.url));
    if (fallback) {
      return fallback;
    }

    return new Response(
      '<!doctype html><html><head><meta charset="utf-8"><title>Pusula</title></head><body><p>Baglanti yok ve cevrimdisi kopya bulunamadi.</p></body></html>',
      {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
        },
        status: 503,
      }
    );
  }
}

async function handleCachedAsset(request) {
  const cache = await caches.open(PUSULA_SHELL_CACHE);
  const cacheKey = normalizeUrl(request.url);
  const cached = await cache.match(cacheKey);

  if (cached) {
    return cached;
  }

  const response = await fetch(request);
  if (response && response.ok) {
    await cache.put(cacheKey, response.clone());
  }
  return response;
}

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('message', (event) => {
  const data = event.data || {};

  if (data.type === 'CONFIGURE_OFFLINE') {
    event.waitUntil(configureOfflineShell(data));
    return;
  }

  if (data.type === 'PURGE_OFFLINE') {
    event.waitUntil(purgeOfflineData());
  }
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin) {
    return;
  }

  const isLogoutRequest = url.pathname.endsWith('/wp-login.php') && url.searchParams.get('action') === 'logout';
  if (isLogoutRequest) {
    event.respondWith(handleLogout(request));
    return;
  }

  if (request.method !== 'GET') {
    return;
  }

  event.respondWith((async () => {
    const config = await readConfig();
    if (!config) {
      return fetch(request);
    }

    const requestUrl = normalizeUrl(request.url);
    const shellUrl = normalizeUrl(config.shellUrl || '');
    const assetUrls = Array.isArray(config.assetUrls) ? config.assetUrls : [];

    if (request.mode === 'navigate' && shellUrl && requestUrl === shellUrl) {
      return handleShellNavigation(request, config);
    }

    if (assetUrls.includes(requestUrl)) {
      return handleCachedAsset(request);
    }

    return fetch(request);
  })());
});
