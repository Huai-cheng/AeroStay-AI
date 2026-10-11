import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Kufi_Arabic } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const kufi = Noto_Kufi_Arabic({
  variable: "--font-arabic",
  subsets: ["arabic"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "AeroStay | Abu Dhabi hotel demand simulator",
  description: "See how changes to flights into Abu Dhabi change hotel guest nights, by country and by month.",
};

export const viewport: Viewport = {
  themeColor: "#070708",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${kufi.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
