'use client';

import clsx from 'clsx';

export default function CodeCard() {
  return (
    <div className={clsx(
      "relative w-[90%] h-[85%] rounded-[20px] bg-[#380b4a] p-3",
      "max-xl:mt-8 max-xl:h-[85%]",
      "max-lg:w-full"
    )}>
      <div className={clsx(
        "relative bg-[#0a0a23] rounded-2xl p-3 w-full h-full",
        "font-['Fira_Code',monospace]",
        "transition-transform duration-300",
        "shadow-[0_8px_20px_rgba(0,0,0,0.9)]",
        "hover:scale-[1.03] hover:transform-[rotateX(2deg)_rotateY(2deg)]"
      )}>
        <div className="flex gap-2 mb-3 justify-start">
          <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
          <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
          <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
        </div>
        <pre className={clsx(
          "font-['Source_Code_Pro',monospace] text-slate-200",
          "rounded-2xl bg-slate-900 p-4 overflow-x-auto",
          "text-[10.5pt]"
        )}>
          <code>
            <span className="text-sky-300 font-bold">import</span> React <span className="text-sky-300 font-bold">from</span> &apos;react&apos;;
            {'\n\n'}
            <span className="text-[#7f848e] italic">(//) 🧩 Hobbies that make me whole</span>
            {'\n'}
            <span className="text-sky-300 font-bold">export default function</span> MyHobbies() {'{'}
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;🐱 Timi and Chocho&quot;</span>);
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;👩‍❤️‍💋‍👨 Winnie&quot;</span>);
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;⚽🏀🏒 Sports&quot;</span>);
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;🎮 HoK FM24&quot;</span>);
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;📷 Nikon Z30&quot;</span>);
            {'\n    '}
            console.<span className='text-[#98c379]'>log</span>(<span className="text-amber-400">&quot;🇨🇳🇨🇦 Beijing Toronto&quot;</span>);
            {'\n\n    '}
            <span className="text-sky-300 font-bold">return</span> <span className={clsx(
              "font-bold bg-[linear-gradient(90deg,#ff00cc,#00ccff,#8000ff,#b300ff,#ff00cc)]",
              "bg-size-[400%_100%] bg-clip-text text-transparent",
              "animate-[neonColorFlow_6s_ease-in-out_infinite]"
            )}>&quot;I love software engineering&quot;</span>;
            {'\n}\n'}
          </code>
        </pre>
      </div>
    </div>
  );
}
