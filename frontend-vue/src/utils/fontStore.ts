/**
 * Font storage — IndexedDB persistence for the custom UI font.
 *
 * Mirrors the legacy frontend's frontend/src/lib/fontStorage.js (same DB
 * name/store/keys so previously saved fonts keep working).
 */

const DB_NAME = 'FontStorage'
const DB_VERSION = 1
const STORE_NAME = 'fonts'

export const FONT_DATA_KEY = 'customFontDataUrl'
export const FONT_NAME_KEY = 'customFontName'

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onerror = () => reject(request.error)
    request.onsuccess = () => resolve(request.result)
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
  })
}

/** Read a value from the font store by key. */
export async function get<T>(key: string): Promise<T | undefined> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly')
    const request = transaction.objectStore(STORE_NAME).get(key)
    request.onsuccess = () => resolve(request.result as T | undefined)
    request.onerror = () => reject(request.error)
  })
}

/** Write a value into the font store. */
export async function save(key: string, value: unknown): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    transaction.objectStore(STORE_NAME).put(value, key)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
}

/** Remove a value from the font store. */
export async function remove(key: string): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    transaction.objectStore(STORE_NAME).delete(key)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
}

export interface StoredFont {
  name: string
  data: string
}

/** Load the stored custom font (name + data URL), or null if none. */
export async function loadFont(): Promise<StoredFont | null> {
  const [name, data] = await Promise.all([
    get<string>(FONT_NAME_KEY),
    get<string>(FONT_DATA_KEY),
  ])
  if (!name || !data) return null
  return { name, data }
}

/** Persist a custom font (name + data URL). */
export async function saveFont(name: string, data: string): Promise<void> {
  await Promise.all([save(FONT_NAME_KEY, name), save(FONT_DATA_KEY, data)])
}

/** Remove the stored custom font. */
export async function removeFont(): Promise<void> {
  await Promise.all([remove(FONT_NAME_KEY), remove(FONT_DATA_KEY)])
}
