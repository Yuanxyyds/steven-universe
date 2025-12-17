'use client';

import { useState, useEffect } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  AiOutlineHome,
  AiOutlineFundProjectionScreen,
} from "react-icons/ai";
import { CgFileDocument } from "react-icons/cg";
import { TbServer2 } from "react-icons/tb";

function NavBar() {
  const [expand, updateExpanded] = useState<boolean>(false);
  const [navColour, updateNavbar] = useState<boolean>(false);

  useEffect(() => {
    function scrollHandler() {
      if (window.scrollY >= 20 || window.innerWidth < 1280) {
        updateNavbar(true);
      } else {
        updateNavbar(false);
      }
    }

    window.addEventListener("scroll", scrollHandler);
    window.addEventListener('resize', scrollHandler);

    // Call once on mount
    scrollHandler();

    return () => {
      window.removeEventListener("scroll", scrollHandler);
      window.removeEventListener('resize', scrollHandler);
    };
  }, []);

  const navItems = [
    { href: "/", icon: AiOutlineHome, label: "Home" },
    { href: "/server", icon: TbServer2, label: "Server" },
    { href: "/project", icon: AiOutlineFundProjectionScreen, label: "Projects" },
    { href: "/resume", icon: CgFileDocument, label: "Resume" },
  ];

  return (
    <nav className={
      clsx("fixed top-0 left-0 right-0 z-50 transition-all duration-300 ease-out px-[8vw] py-5 text-xl",
        navColour ? "bg-[rgb(9,0,14)] backdrop-blur-[15px] shadow-[0_0_20px_rgba(89,4,168,0.3)]" : "")}>

      <div className="flex items-center justify-between w-full">
        {/* Brand */}
        <Link href="/" className="text-white font-bold text-xl no-underline">
          STEV.LIU
        </Link>

        {/* Mobile Menu Toggle */}
        <button
          className="xl:hidden relative bg-transparent border-0 p-2 h-10 w-10 focus:outline-none"
          onClick={() => updateExpanded(!expand)}
          aria-label="Toggle navigation">

          <span
            className={clsx(
              "block bg-gray-100 h-1 w-6.75 my-1.25 transition-transform duration-350 ease-in-out",
              expand ? "absolute left-3 top-4 rotate-135 opacity-90" : "rotate-0 opacity-100"
            )}
          />
          <span
            className={clsx(
              "block bg-gray-100 h-1 w-6.75 my-1.25",
              expand ? "h-3 invisible bg-transparent" : "visible"
            )}
          />
          <span
            className={clsx(
              "block bg-gray-100 h-1 w-6.75 my-1.25 transition-transform duration-350 ease-in-out",
              expand ? "absolute left-3 top-4 rotate-[-135deg] opacity-90" : "rotate-0 opacity-100"
            )}
          />
        </button>

        {/* Desktop Navigation */}
        <ul className="hidden xl:flex items-center justify-center ml-auto">
          {navItems.map((item) => (
            <li key={item.href} className="relative ml-5">
              <Link
                href={item.href}
                className="group relative inline-flex items-center px-4 py-3 text-white font-normal"
              >
                <span
                  className={clsx(
                    "relative inline-flex items-center gap-1 text-[1.2rem]",
                    "after:content-[''] after:absolute after:left-0 after:-bottom-1",
                    "after:h-1 after:w-full after:bg-primary after:rounded-full",
                    "after:scale-x-0 after:origin-left after:transition-transform",
                    "after:duration-300 after:ease-out",
                    "group-hover:after:scale-x-100"
                  )}
                >
                  <item.icon className="mb-0.5" />
                  {item.label}
                </span>
              </Link>
            </li>
          ))}
        </ul>

        {/* Mobile Navigation */}
        <div
          className={clsx(
            "xl:hidden fixed top-15 left-0 right-0 bg-[rgb(9,0,14)] overflow-hidden transition-all duration-300 ease-in-out",
            expand ? "max-h-100 opacity-100" : "max-h-0 opacity-0"
          )}
        >
          <ul className="flex flex-col items-center justify-center p-5 m-0 list-none">
            {navItems.map((item) => (
              <li key={item.href} className="w-full text-center text-[1.4rem]">
                <Link
                  href={item.href}
                  onClick={() => updateExpanded(false)}
                  className="text-white no-underline px-4 py-3 font-normal transition-all duration-300 ease-out
                    inline-flex items-center justify-center gap-2 hover:text-primary"
                >
                  <item.icon className="mb-0.5" /> {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </nav>
  );
}

export default NavBar;
