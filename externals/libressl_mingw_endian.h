/* Force-included when building LibreSSL with MinGW (msys2): newer clang rejects the implicit
 * htobe32/htobe64 calls in crypto_internal.h because MinGW's headers do not declare them. */
#ifndef AZAHAR_LIBRESSL_MINGW_ENDIAN_H
#define AZAHAR_LIBRESSL_MINGW_ENDIAN_H

#include <stdint.h>

#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#ifndef htobe16
#define htobe16(x) __builtin_bswap16((uint16_t)(x))
#endif
#ifndef htobe32
#define htobe32(x) __builtin_bswap32((uint32_t)(x))
#endif
#ifndef htobe64
#define htobe64(x) __builtin_bswap64((uint64_t)(x))
#endif
#ifndef be16toh
#define be16toh(x) __builtin_bswap16((uint16_t)(x))
#endif
#ifndef be32toh
#define be32toh(x) __builtin_bswap32((uint32_t)(x))
#endif
#ifndef be64toh
#define be64toh(x) __builtin_bswap64((uint64_t)(x))
#endif
#ifndef htole16
#define htole16(x) ((uint16_t)(x))
#endif
#ifndef htole32
#define htole32(x) ((uint32_t)(x))
#endif
#ifndef htole64
#define htole64(x) ((uint64_t)(x))
#endif
#ifndef le16toh
#define le16toh(x) ((uint16_t)(x))
#endif
#ifndef le32toh
#define le32toh(x) ((uint32_t)(x))
#endif
#ifndef le64toh
#define le64toh(x) ((uint64_t)(x))
#endif
#endif /* little endian */

#endif
