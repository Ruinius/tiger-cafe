/**
 * Compute a quick hash of a file for duplicate detection.
 * Uses the first 5KB of the file to generate a SHA-256 hash.
 * 
 * @param {File} file - The file to hash
 * @returns {Promise<string>} - Hex string of the hash
 */
export async function computeQuickHash(file) {
    // Use first 5KB (5120 bytes)
    const sliceSize = 5120;
    const slice = file.slice(0, sliceSize);
    const arrayBuffer = await slice.arrayBuffer();

    // Use Web Crypto API for performance
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);

    // Convert buffer to hex string
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    return hashHex;
}
