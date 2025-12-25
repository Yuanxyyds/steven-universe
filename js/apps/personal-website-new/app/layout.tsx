import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/common/Navbar";
import Loader from "@/components/common/Loader";
import ChatbotWrapper from "@/components/common/ChatbotWrapper";
import NeonTrail from "@/components/effects/NeonTrail";
import FooterWrapper from "@/components/common/FooterWrapper";

export const metadata: Metadata = {
  title: "Hongyuan (Steven) Liu | AI Developer",
  description: "Portfolio of Hongyuan (Steven) Liu, M.Eng. student at UPenn specializing in Machine Learning, Software Engineering, and UI/UX Design.",
  icons: {
    icon: "/favicon.png",
  },
  openGraph: {
    title: "Hongyuan (Steven) Liu | AI Developer",
    description: "Portfolio of Hongyuan (Steven) Liu, M.Eng. student at UPenn specializing in Machine Learning, Software Engineering, and UI/UX Design.",
    url: "https://www.liustev6.ca",
    siteName: "Hongyuan (Steven) Liu",
    images: [
      {
        url: "https://www.liustev6.ca/cover.png",
        width: 1200,
        height: 630,
        alt: "Hongyuan (Steven) Liu Portfolio",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Hongyuan (Steven) Liu | AI Developer",
    description: "Hongyuan (Steven) Liu's personal portfolio. I'm Steven, a Master's student at the University of Pennsylvania, specializing in Machine Learning, Software Engineering and UI/UX Design.",
    images: ["https://www.liustev6.ca/cover.png"],
  },
  other: {
    "google-site-verification": "your-verification-code", // Update if you have one
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Loader />
        <NeonTrail />
        <NavBar />
        {children}
        <FooterWrapper />
        <ChatbotWrapper />
      </body>
    </html>
  );
}
