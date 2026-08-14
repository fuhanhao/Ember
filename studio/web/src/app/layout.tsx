import type { Metadata } from "next";
import Script from "next/script";
import { Geist } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Ember - 全球AI信息聚合与智能加工平台",
  description: "从全球信息流中提炼权威、可读的智能时代编年史，聚合、加工、再创造。",
  applicationName: "Ember",
  keywords: ["AI", "信息聚合", "智能简报", "Ember", "人工智能"],
  icons: {
    icon: "/icon.svg",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={geistSans.variable} suppressHydrationWarning>
      <head>
        {/* Prevent flash of wrong theme on load */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function() {
            var t = localStorage.getItem('ember_theme') || 'dark';
            if (t === 'dark') document.documentElement.classList.add('dark');
          })();
        ` }} />
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
        <Script id="bfcache-reload" strategy="afterInteractive">{`
          window.addEventListener('pageshow', function(e) {
            if (e.persisted) { window.location.reload(); }
          });
        `}</Script>
      </body>
    </html>
  );
}
