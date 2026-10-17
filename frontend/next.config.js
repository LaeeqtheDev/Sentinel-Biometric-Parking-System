/** @type {import('next').NextConfig} */

// Images are served by the API through signed links (/api/files/...), so
// allow the API host from NEXT_PUBLIC_API_URL instead of hard-coding localhost.
const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api');

// Only these sites may embed Sentinel in an iframe. Every other site is
// refused by the browser (clickjacking protection). Override with
// FRAME_ANCESTORS="https://a.com https://b.com" at build time.
const frameAncestors =
  process.env.FRAME_ANCESTORS || "'self' https://northfoundry.co https://*.northfoundry.co";

const nextConfig = {
  reactStrictMode: true,
  // Small self-contained server bundle for the Docker image.
  output: 'standalone',
  poweredByHeader: false,
  images: {
    remotePatterns: [
      {
        protocol: apiUrl.protocol.replace(':', ''),
        hostname: apiUrl.hostname,
        port: apiUrl.port,
        pathname: '/api/files/**',
      },
    ],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          // frame-ancestors replaces X-Frame-Options (which can't allow-list a domain).
          { key: 'Content-Security-Policy', value: `frame-ancestors ${frameAncestors};` },
          // Camera and passkeys allowed for the page itself and for the northfoundry.co embed.
          {
            key: 'Permissions-Policy',
            value: 'camera=(self "https://northfoundry.co"), publickey-credentials-get=(self "https://northfoundry.co"), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
