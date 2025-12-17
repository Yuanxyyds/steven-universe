import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/common/Navbar";
import Footer from "@/components/common/Footer";

export const metadata: Metadata = {
  title: "Steven Liu - Portfolio",
  description: "Personal portfolio of Steven Liu - Full-Stack Developer & ML Engineer",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        {children}
        <Footer />
      </body>
    </html>
  );
}
