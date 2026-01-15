/**
 * Crypto utilities for encrypting/decrypting sensitive data in localStorage.
 * Uses Web Crypto API with AES-GCM encryption.
 */

const CRYPTO_KEY_NAME = 'epub-translator-crypto-key'
const ALGORITHM = 'AES-GCM'
const KEY_LENGTH = 256

// Generate a random encryption key
async function generateKey(): Promise<CryptoKey> {
  return await crypto.subtle.generateKey(
    { name: ALGORITHM, length: KEY_LENGTH },
    true, // extractable
    ['encrypt', 'decrypt']
  )
}

// Export key to storable format
async function exportKey(key: CryptoKey): Promise<string> {
  const exported = await crypto.subtle.exportKey('raw', key)
  return btoa(String.fromCharCode(...new Uint8Array(exported)))
}

// Import key from stored format
async function importKey(keyData: string): Promise<CryptoKey> {
  const raw = Uint8Array.from(atob(keyData), c => c.charCodeAt(0))
  return await crypto.subtle.importKey(
    'raw',
    raw,
    { name: ALGORITHM, length: KEY_LENGTH },
    true,
    ['encrypt', 'decrypt']
  )
}

// Get or create the encryption key
async function getOrCreateKey(): Promise<CryptoKey> {
  const stored = localStorage.getItem(CRYPTO_KEY_NAME)

  if (stored) {
    try {
      return await importKey(stored)
    } catch {
      // Key corrupted, regenerate
      console.warn('Crypto key corrupted, regenerating...')
    }
  }

  // Generate new key
  const key = await generateKey()
  const exported = await exportKey(key)
  localStorage.setItem(CRYPTO_KEY_NAME, exported)
  return key
}

/**
 * Encrypt a string value.
 * Returns base64 encoded string containing IV + ciphertext.
 */
export async function encrypt(plaintext: string): Promise<string> {
  if (!plaintext) return ''

  try {
    const key = await getOrCreateKey()
    const iv = crypto.getRandomValues(new Uint8Array(12)) // 96-bit IV for GCM
    const encoded = new TextEncoder().encode(plaintext)

    const ciphertext = await crypto.subtle.encrypt(
      { name: ALGORITHM, iv },
      key,
      encoded
    )

    // Combine IV + ciphertext and encode as base64
    const combined = new Uint8Array(iv.length + ciphertext.byteLength)
    combined.set(iv)
    combined.set(new Uint8Array(ciphertext), iv.length)

    return btoa(String.fromCharCode(...combined))
  } catch (error) {
    console.error('Encryption failed:', error)
    throw new Error('Failed to encrypt data')
  }
}

/**
 * Decrypt a base64 encoded encrypted string.
 * Input should be IV + ciphertext from encrypt().
 * If decryption fails (e.g., plaintext data from before encryption was added),
 * returns the original string to support migration.
 */
export async function decrypt(encrypted: string): Promise<string> {
  if (!encrypted) return ''

  // Check if it looks like encrypted data (base64 with minimum length)
  // Encrypted data: 12 bytes IV + at least 16 bytes ciphertext = 28+ bytes = 38+ base64 chars
  const looksEncrypted = encrypted.length >= 38 && /^[A-Za-z0-9+/]+=*$/.test(encrypted)

  if (!looksEncrypted) {
    // Likely plaintext API key from before encryption was added
    // Return as-is to support migration
    return encrypted
  }

  try {
    const key = await getOrCreateKey()
    const combined = Uint8Array.from(atob(encrypted), c => c.charCodeAt(0))

    // Must have at least 12 bytes IV + 16 bytes ciphertext
    if (combined.length < 28) {
      // Too short to be encrypted, return as plaintext
      return encrypted
    }

    // Extract IV (first 12 bytes) and ciphertext
    const iv = combined.slice(0, 12)
    const ciphertext = combined.slice(12)

    const decrypted = await crypto.subtle.decrypt(
      { name: ALGORITHM, iv },
      key,
      ciphertext
    )

    return new TextDecoder().decode(decrypted)
  } catch (error) {
    // Decryption failed - likely plaintext data from before encryption
    // Return original string to preserve existing API keys during migration
    console.warn('Decryption failed, treating as plaintext (migration):', error)
    return encrypted
  }
}

/**
 * Check if a string looks like it's encrypted (base64 with sufficient length).
 * Used for migration from plaintext to encrypted storage.
 */
export function isEncrypted(value: string): boolean {
  if (!value || value.length < 20) return false
  // Check if it's valid base64 and has minimum length for IV + some data
  try {
    const decoded = atob(value)
    // Minimum: 12 bytes IV + at least 16 bytes ciphertext (AES block)
    return decoded.length >= 28
  } catch {
    return false
  }
}

/**
 * Encrypt an object's specified fields.
 */
export async function encryptFields<T extends Record<string, unknown>>(
  obj: T,
  fields: (keyof T)[]
): Promise<T> {
  const result = { ...obj }
  for (const field of fields) {
    const value = obj[field]
    if (typeof value === 'string' && value) {
      (result as Record<string, unknown>)[field as string] = await encrypt(value)
    }
  }
  return result
}

/**
 * Decrypt an object's specified fields.
 */
export async function decryptFields<T extends Record<string, unknown>>(
  obj: T,
  fields: (keyof T)[]
): Promise<T> {
  const result = { ...obj }
  for (const field of fields) {
    const value = obj[field]
    if (typeof value === 'string' && value) {
      (result as Record<string, unknown>)[field as string] = await decrypt(value)
    }
  }
  return result
}

