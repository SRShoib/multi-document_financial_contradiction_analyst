/**
 * Ambient dark-mode background: three slow-drifting aurora blobs, a faint
 * fading grid, and a subtle film-grain overlay. Pure CSS animation (see
 * `globals.css`) — no client JS needed, so this can render on the server.
 */
export function BackgroundFx() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-background" />
      <div
        className="aurora-blob animate-drift-a left-[-10%] top-[-15%] h-[560px] w-[560px] bg-iris-1/25"
      />
      <div
        className="aurora-blob animate-drift-b right-[-15%] top-[5%] h-[620px] w-[620px] bg-iris-2/20"
      />
      <div
        className="aurora-blob animate-drift-c left-1/2 top-[55%] h-[680px] w-[680px] bg-iris-3/15"
      />
      <div className="grid-fade" />
      <div className="noise-overlay" />
    </div>
  );
}
