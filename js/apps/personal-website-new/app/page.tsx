'use client';

import { useEffect } from "react";
import { AiFillGithub, AiFillInstagram } from "react-icons/ai";
import { FaLinkedinIn } from "react-icons/fa";
import Typewriter from "typewriter-effect";
import ProgressCard from "@/components/home/ProgressCard";
import CodeCard from "@/components/home/CodeCard";
import { ScrollImage, StickyText } from "@/components/home/Gallery";

interface AnimatedLineElement {
    headerId: string;
    lineId: string;
}

export default function Home() {
    useEffect(() => {
        const elements: AnimatedLineElement[] = [
            { headerId: 'whoami', lineId: 'whoami-line' },
            { headerId: 'fullstack', lineId: 'fullstack-line' },
            { headerId: 'contact', lineId: 'contact-line' },
        ];

        function handleScroll() {
            const viewportHeight = window.innerHeight;

            elements.forEach(({ headerId, lineId }) => {
                const header = document.getElementById(headerId);
                const line = document.getElementById(lineId);

                if (!header || !line) return;

                const rect = header.getBoundingClientRect();
                const distanceFromBottom = viewportHeight - rect.top;
                const scrollRatio = distanceFromBottom / viewportHeight;

                let widthPercent = 0;
                if (scrollRatio < 0.2) {
                    widthPercent = 0;
                } else if (scrollRatio >= 0.5) {
                    widthPercent = 100;
                } else {
                    widthPercent = ((scrollRatio - 0.2) / (0.5 - 0.2)) * 100;
                }

                widthPercent = Math.min(Math.max(widthPercent, 0), 100);
                line.style.width = `${widthPercent}%`;
            });
        }

        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <section>
            {/* Home Section */}
            <div id="home" className="w-full text-left text-[whitesmoke] m-0 p-0">
                <div className="relative min-h-screen w-screen m-0 p-0 overflow-hidden">
                    <video
                        className="absolute top-0 left-0 w-full h-full object-cover -z-10 pointer-events-none"
                        src="/home/bg.mp4"
                        autoPlay
                        muted
                        loop
                        playsInline
                    />
                    <div className="w-full px-[8vw] py-[10vh]">
                        <div className="w-full">
                            <div className="w-full md:w-1/2 lg:w-5/12 xl:w-5/12">
                                <h1 className="font-light opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mb-0 delay-0">
                                    MAKE IT
                                </h1>
                                <h1 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards]">
                                    <Typewriter
                                        options={{
                                            strings: [
                                                "INNOVATIVE",
                                                "IMPACTFUL",
                                            ],
                                            cursor: '|',
                                            autoStart: true,
                                            loop: true,
                                            deleteSpeed: 80,
                                        }}
                                    />
                                </h1>

                                <h5 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] ml-1 font-bold delay-[2s]">
                                    I&apos;m Steven, a Master&apos;s student at the University of Pennsylvania, specializing in Machine Learning, Software Engineering and UI/UX Design.
                                </h5>
                            </div>
                        </div>
                    </div>
                </div>

                {/* About Section */}
                <div id="about" className="w-full px-[8vw] py-[10vh]">
                    <div className="flex flex-wrap -mx-4">
                        <div className="w-full xl:w-2/3 px-4">
                            <div className="mb-4">
                                <h2 id="whoami" className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mb-0">WHO AM I</h2>
                                <div id="whoami-line" className="h-1 bg-primary rounded-full transition-all duration-300"></div>
                            </div>

                            <p className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-12">
                                I&apos;m Hongyuan (Steven) Liu. I recently graduated from University of Toronto (June 2025), where I completed
                                my Bachelor of Science in Computer Science with a GPA 3.90/4.0. Starting Fall 2025, I will pursue a Master
                                of Engineering in AI at the University of Pennsylvania. I previously worked as a
                                <i> <b className="text-primary"> Full-Stack Mobile Developer at Johnson Controls </b> </i> and served
                                as the  <i> <b className="text-primary">  Founder of the Campus Eats. </b> </i>
                            </p>

                            <p className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-4">I am expertise in
                                <i>
                                    <b className="text-primary"> Machine Learning, Full-Stack Mobile/Web Development, Software Business, and UI/UX Design. </b>
                                </i>
                                Besides, I am actively contributing to a diverse range of 10+ projects, software
                                business startups, over 1000+ contribution on github.
                            </p>
                        </div>
                        <div className="w-full xl:w-1/3 px-4 flex justify-center items-center">
                            <video src='/home/avatar.mp4' autoPlay muted loop playsInline style={{ maxHeight: "400px" }} />
                        </div>
                    </div>
                </div>

                {/* What I Do Section */}
                <div className="w-full px-[8vw] py-[10vh]">
                    <div className="flex flex-wrap -mx-4 items-stretch">
                        <div className="w-full md:w-10/12 lg:w-2/3 xl:w-1/2 px-4">
                            <div className="mb-4">
                                <h2 id="fullstack" className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mb-0">WHAT I DO</h2>
                                <div id="fullstack-line" className="h-1 bg-primary rounded-full transition-all duration-300"></div>
                            </div>
                            <h5 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mb-4">
                                I create engaging, interactive software powered by cutting-edge technologies.
                            </h5>
                            <div className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards]">
                                <ProgressCard />
                            </div>
                        </div>
                        <div className="w-full md:w-10/12 lg:w-2/3 xl:w-1/2 px-4 flex flex-col">
                            <div className="rounded-[20px] bg-[#380b4a] mt-auto p-3 w-[90%] h-[85%] max-xl:mt-8 max-xl:h-[85%] max-sm:w-full opacity-0 animate-[fadeIn_1s_ease-in-out_forwards]">
                                <CodeCard />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Gallery Section */}
                <StickyText text="There are many other things I do" />
                <div id="gallery" className="w-full px-[8vw] py-[10vh]">
                    <div className="relative mt-[5vh] pt-[45vh] pb-[10vh] px-0">
                        <div className="flex flex-wrap m-0 p-0">
                            <div id="first-image" className="w-full md:w-1/2 m-0 p-0 text-center">
                                <ScrollImage src="/home/lake.JPG" speed={1} z={0} />
                                <p className="w-[70%] mx-auto my-0.5 mt-[15%] mb-[15%]">
                                    Photography is one of my creative outlets — here&apos;s a glimpse into my gallery.
                                </p>
                            </div>
                            <div className="w-full md:w-1/2 m-0 p-0">
                                <ScrollImage src="/home/winnie.JPG" speed={0.8} wrapperWidth="70%"
                                    initialOffset={-20} />
                            </div>
                        </div>
                        <div className="flex flex-wrap m-0 p-0">
                            <div className="w-full md:w-1/2 m-0 p-0">
                                <ScrollImage src="/home/light.JPG" speed={1.1} initialOffset={10} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Contact Section */}
                <div
                    id="contact-section"
                    className="w-full mb-[10vh] bg-[url('/home/get-in-touch.png')] bg-no-repeat bg-right-bottom bg-contain max-xl:bg-[linear-gradient(rgba(0,0,0,0.7),rgba(0,0,0,0.7)),url('/home/get-in-touch.png')]"
                >
                    <div className="w-full px-[8vw] py-[10vh]">
                        <div className="flex flex-wrap -mx-4">
                            <div className="w-full xl:w-2/3 px-4">
                                <div className="mb-4">
                                    <h2 id="contact" className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mb-0">CONTACT ME AT</h2>
                                    <div id="contact-line" className="h-1 bg-primary rounded-full transition-all duration-300"></div>
                                </div>

                                <div id="contact" className="w-full p-0">
                                    <h4 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-12">
                                        <strong className="text-primary">Location:</strong> Toronto ON, Vancouver BC
                                    </h4>
                                    <h4 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-3">
                                        <strong className="text-primary">Email:</strong> liuhongyuan2001 AT
                                        gmail.com
                                    </h4>
                                    <h4 className="opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-3">
                                        <strong className="text-primary">Phone:</strong> +1 (647)-309-9649
                                    </h4>

                                    <ul className="flex text-center p-0 text-white justify-start list-none mb-[100px] opacity-0 animate-[fadeIn_1s_ease-in-out_forwards] mt-3">
                                        <li className="me-4">
                                            <a
                                                href="https://github.com/Yuanxyyds"
                                                target="_blank"
                                                rel="noreferrer"
                                                className="relative inline-block w-10 h-10 text-xl leading-[2em] bg-white text-black rounded-full transition-all duration-500 hover:text-primary before:content-[''] before:absolute before:top-0 before:left-0 before:w-full before:h-full before:rounded-full before:transition-all before:duration-500 before:-z-10 before:scale-115 before:animate-[neonBluePurpleGradient_3s_infinite]"
                                            >
                                                <AiFillGithub />
                                            </a>
                                        </li>
                                        <li className="me-4">
                                            <a
                                                href="https://www.linkedin.com/in/liustev6/"
                                                target="_blank"
                                                rel="noreferrer"
                                                className="relative inline-block w-10 h-10 text-xl leading-[2em] bg-white text-black rounded-full transition-all duration-500 hover:text-primary before:content-[''] before:absolute before:top-0 before:left-0 before:w-full before:h-full before:rounded-full before:transition-all before:duration-500 before:-z-10 before:scale-115 before:animate-[neonBluePurpleGradient_3s_infinite]"
                                            >
                                                <FaLinkedinIn />
                                            </a>
                                        </li>
                                        <li className="me-4">
                                            <a
                                                href="https://www.instagram.com/yuanxyyds/"
                                                target="_blank"
                                                rel="noreferrer"
                                                className="relative inline-block w-10 h-10 text-xl leading-[2em] bg-white text-black rounded-full transition-all duration-500 hover:text-primary before:content-[''] before:absolute before:top-0 before:left-0 before:w-full before:h-full before:rounded-full before:transition-all before:duration-500 before:-z-10 before:scale-115 before:animate-[neonBluePurpleGradient_3s_infinite]"
                                            >
                                                <AiFillInstagram />
                                            </a>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </section >
    );
}
