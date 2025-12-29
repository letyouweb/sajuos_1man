/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // 🔥 P0: Production 환경에서 소스맵 활성화 (디버깅용)
  productionBrowserSourceMaps: true,
  
  // 🔥 P0: rewrite 제거 - 프론트엔드는 https://api.sajuos.com 절대주소로 직접 호출
  // Vercel의 DNS_HOSTNAME_RESOLVED_PRIVATE 에러 방지
}

module.exports = nextConfig
