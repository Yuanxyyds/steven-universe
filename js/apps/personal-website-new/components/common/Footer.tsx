'use client';

import {
    AiFillGithub,
    AiFillInstagram,
} from "react-icons/ai";
import { FaLinkedinIn } from "react-icons/fa";

function Footer() {
    const date = new Date();
    const year = date.getFullYear();

    return (
        <section>
            <div className="w-full py-2.5 bottom-0">
                <div className="flex flex-wrap">
                    <div className="w-full md:w-1/3 text-center">
                        <p className="text-base text-white my-2">Developed by Steven Liu</p>
                    </div>
                    <div className="w-full md:w-1/3 text-center">
                        <p className="text-base text-white my-2">Copyright © {year} SL</p>
                    </div>
                    <div className="w-full md:w-1/3">
                        <ul className="flex justify-center text-center p-0 m-0 list-none">
                            <div className="pr-7.5">
                                <a
                                    href="https://github.com/Yuanxyyds"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="relative text-[1.2em] text-white transition-colors duration-500 hover:text-secondary"
                                >
                                    <AiFillGithub />
                                </a>
                            </div>
                            <div className="pr-7.5">
                                <a
                                    href="https://www.linkedin.com/in/liustev6/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="relative text-[1.2em] text-white transition-colors duration-500 hover:text-secondary"
                                >
                                    <FaLinkedinIn />
                                </a>
                            </div>
                            <div className="pr-[30px]">
                                <a
                                    href="https://www.instagram.com/yuanxyyds/"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="relative text-[1.2em] text-white transition-colors duration-500 hover:text-secondary"
                                >
                                    <AiFillInstagram />
                                </a>
                            </div>
                        </ul>
                    </div>
                </div>
            </div>
        </section>
    );
}

export default Footer;
