import { NextResponse } from 'next/server'

export function middleware() {
  return new NextResponse('Service suspended due to pending payment.', {
    status: 403,
    headers: {
      'Cache-Control': 'no-store',
    },
  })
}
