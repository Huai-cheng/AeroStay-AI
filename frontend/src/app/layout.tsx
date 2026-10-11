import type { Metadata, Viewport } from "next";
import { Inter, Noto_Kufi_Arabic } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
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
    <html lang="en" className={`${inter.variable} ${kufi.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
