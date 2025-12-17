'use client';

import './code-card.css';

export default function CodeCard() {
  return (
    <div className="code-card">
      <div className="card-header">
        <div className="dot red" />
        <div className="dot yellow" />
        <div className="dot green" />
      </div>
      <pre className="code-block">
        <code>
          <span className="keyword">import</span> React <span className="keyword">from</span> &apos;react&apos;;
          {'\n\n'}
          <span className="comment">(//) 🧩 Hobbies that make me whole</span>
          {'\n'}
          <span className="keyword">export default function</span> MyHobbies() {'{'}
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;🐱 Timi and Chocho&quot;</span>);
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;👩‍❤️‍💋‍👨 Winnie&quot;</span>);
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;⚽🏀🏒 Sports&quot;</span>);
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;🎮 HoK FM24&quot;</span>);
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;📷 Nikon Z30&quot;</span>);
          {'\n    '}
          console.<span className='highlight'>log</span>(<span className="string">&quot;🇨🇳🇨🇦 Beijing Toronto&quot;</span>);
          {'\n\n    '}
          <span className="keyword">return</span> <span className="neon-text">&quot;I love software engineering&quot;</span>;
          {'\n}\n'}
        </code>
      </pre>
    </div>
  );
}
