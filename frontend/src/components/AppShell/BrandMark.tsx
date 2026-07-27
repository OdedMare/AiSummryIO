/**
 * SumOrAI logo mark. The three stacked bars collapse left-to-right — many
 * source records condensing into one line — with an orbiting spark for the
 * agent. Drawn inline rather than as an icon import so the gradient can pick
 * up the brand tokens and animate with the shell.
 */
export default function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      aria-hidden="true" focusable="false">
      <path d="M4 6.5h13" stroke="currentColor" strokeWidth="2.4"
        strokeLinecap="round" opacity="0.95" />
      <path d="M4 12h9" stroke="currentColor" strokeWidth="2.4"
        strokeLinecap="round" opacity="0.72" />
      <path d="M4 17.5h5.5" stroke="currentColor" strokeWidth="2.4"
        strokeLinecap="round" opacity="0.5" />
      <path d="M18.4 13.6l.72 2.06 2.06.72-2.06.72-.72 2.06-.72-2.06-2.06-.72
        2.06-.72.72-2.06z" fill="currentColor" />
    </svg>
  );
}
