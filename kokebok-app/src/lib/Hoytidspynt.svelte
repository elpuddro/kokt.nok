<script lang="ts">
  let { hoytid }: { hoytid: string } = $props();
</script>

<div class="pynt-lag" aria-hidden="true">
  {#if hoytid === "jul"}
    <svg class="snofnugg s1" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.35">
      <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
      <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
      <line x1="10" y1="1" x2="7" y2="4"/><line x1="10" y1="1" x2="13" y2="4"/>
      <line x1="10" y1="19" x2="7" y2="16"/><line x1="10" y1="19" x2="13" y2="16"/>
    </svg>
    <svg class="snofnugg s2" viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.25">
      <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
      <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
    </svg>
    <svg class="snofnugg s3" viewBox="0 0 20 20" width="11" height="11" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.20">
      <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
      <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
    </svg>
  {:else if hoytid === "paske"}
    <svg class="egg e1" viewBox="0 0 24 30" width="22" height="28">
      <ellipse cx="12" cy="16" rx="9" ry="12" fill="#f9d6a0" stroke="#e8b96a" stroke-width="1"/>
    </svg>
    <svg class="egg e2" viewBox="0 0 24 30" width="18" height="24">
      <ellipse cx="12" cy="16" rx="9" ry="12" fill="#b8dfc8" stroke="#7dbb99" stroke-width="1"/>
    </svg>
    <svg class="egg e3" viewBox="0 0 24 30" width="20" height="26">
      <ellipse cx="12" cy="16" rx="9" ry="12" fill="#d4b8e0" stroke="#a87cc4" stroke-width="1"/>
    </svg>
  {:else if hoytid === "mai17"}
    <svg class="konfetti k1" viewBox="0 0 10 18" width="9" height="16">
      <rect width="10" height="18" rx="2" fill="#ef2d3b" transform="rotate(-18 5 9)"/>
    </svg>
    <svg class="konfetti k2" viewBox="0 0 10 18" width="9" height="16">
      <rect width="10" height="18" rx="2" fill="#ffffff" stroke="#ddd" stroke-width="0.5" transform="rotate(8 5 9)"/>
    </svg>
    <svg class="konfetti k3" viewBox="0 0 10 18" width="9" height="16">
      <rect width="10" height="18" rx="2" fill="#003087" transform="rotate(-6 5 9)"/>
    </svg>
  {:else if hoytid === "sankthans"}
    <svg class="flamme" viewBox="0 0 24 36" width="22" height="32" fill="none">
      <path d="M12 34 C6 28, 2 22, 6 14 C8 10, 10 8, 12 2 C14 8, 18 12, 17 18 C16 22, 14 26, 12 34Z"
            fill="#ff8c00" opacity="0.7"/>
      <path d="M12 30 C9 25, 7 20, 10 15 C11 12, 12 10, 12 6 C13 10, 16 14, 15 19 C14 23, 13 26, 12 30Z"
            fill="#ffcc00" opacity="0.8"/>
    </svg>
  {:else if hoytid === "halloween"}
    <svg class="spindelvev sv1" viewBox="0 0 40 40" width="36" height="36" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.30">
      <line x1="20" y1="0" x2="20" y2="40"/>
      <line x1="0" y1="20" x2="40" y2="20"/>
      <line x1="0" y1="0" x2="40" y2="40"/>
      <line x1="40" y1="0" x2="0" y2="40"/>
      <circle cx="20" cy="20" r="6" fill="none"/>
      <circle cx="20" cy="20" r="13" fill="none"/>
    </svg>
    <svg class="spindelvev sv2" viewBox="0 0 30 30" width="26" height="26" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.20">
      <line x1="15" y1="0" x2="15" y2="30"/>
      <line x1="0" y1="15" x2="30" y2="15"/>
      <line x1="0" y1="0" x2="30" y2="30"/>
      <line x1="30" y1="0" x2="0" y2="30"/>
      <circle cx="15" cy="15" r="5" fill="none"/>
      <circle cx="15" cy="15" r="10" fill="none"/>
    </svg>
    <svg class="spindelvev sv3" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.18">
      <line x1="12" y1="0" x2="12" y2="24"/>
      <line x1="0" y1="12" x2="24" y2="12"/>
      <line x1="0" y1="0" x2="24" y2="24"/>
      <line x1="24" y1="0" x2="0" y2="24"/>
      <circle cx="12" cy="12" r="4" fill="none"/>
    </svg>
  {:else if hoytid === "valentins"}
    <svg class="hjerte h1" viewBox="0 0 24 22" width="20" height="18" fill="none" stroke="currentColor" stroke-width="1.4" opacity="0.45">
      <path d="M12 20 C12 20, 2 13, 2 7 A5 5 0 0 1 12 5 A5 5 0 0 1 22 7 C22 13, 12 20, 12 20Z"/>
    </svg>
    <svg class="hjerte h2" viewBox="0 0 24 22" width="14" height="13" fill="none" stroke="currentColor" stroke-width="1.4" opacity="0.30">
      <path d="M12 20 C12 20, 2 13, 2 7 A5 5 0 0 1 12 5 A5 5 0 0 1 22 7 C22 13, 12 20, 12 20Z"/>
    </svg>
  {/if}
</div>

<style>
  .pynt-lag {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }

  .snofnugg {
    position: absolute;
    right: 12px;
    animation: falle linear infinite;
    color: var(--accent-light, #aac8e8);
  }
  .s1 { top: -18px; animation-duration: 8s; animation-delay: 0s; }
  .s2 { top: -14px; right: 30px; animation-duration: 11s; animation-delay: 3s; }
  .s3 { top: -11px; right: 48px; animation-duration: 9s; animation-delay: 6s; }

  @keyframes falle {
    0%   { transform: translateY(0)   rotate(0deg); }
    100% { transform: translateY(80px) rotate(180deg); }
  }

  .egg {
    position: absolute;
    bottom: 4px;
    opacity: 0.55;
  }
  .e1 { left: 12px; }
  .e2 { left: 44px; bottom: 6px; }
  .e3 { left: 74px; }

  .konfetti {
    position: absolute;
    top: 6px;
    opacity: 0.55;
  }
  .k1 { right: 16px; }
  .k2 { right: 30px; top: 10px; }
  .k3 { right: 44px; top: 5px; }

  .flamme {
    position: absolute;
    right: 14px;
    bottom: 2px;
    animation: pulsere ease-in-out infinite;
    animation-duration: 2.4s;
    transform-origin: bottom center;
  }

  @keyframes pulsere {
    0%, 100% { transform: scaleY(1)   scaleX(1); }
    50%       { transform: scaleY(1.06) scaleX(0.96); }
  }

  .spindelvev {
    position: absolute;
    top: 0;
    color: var(--text-muted, #b09cc0);
  }
  .sv1 { left: 0; }
  .sv2 { left: 28px; top: 2px; }
  .sv3 { right: 0; }

  .hjerte {
    position: absolute;
    bottom: 4px;
    color: var(--accent, #c2185b);
    animation: flyte ease-in-out infinite;
  }
  .h1 { right: 18px; animation-duration: 6s; animation-delay: 0s; }
  .h2 { right: 44px; animation-duration: 8s; animation-delay: 2s; }

  @keyframes flyte {
    0%   { transform: translateY(0);    opacity: 0.45; }
    50%  { transform: translateY(-18px); opacity: 0.20; }
    100% { transform: translateY(0);    opacity: 0.45; }
  }
</style>
