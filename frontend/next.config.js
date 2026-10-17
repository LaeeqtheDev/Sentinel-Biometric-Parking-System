/** @type {import('next').NextConfig} */

// Images are served by the API through signed links (/api/files/...), so
// allow the API host from NEXT_PUBLIC_API_URL instead of hard-coding localhost.
const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api');

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
          { key: 'X-Frame-Options', value: 'DENY' },
          // Camera is needed by the live console and face capture.
          { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
