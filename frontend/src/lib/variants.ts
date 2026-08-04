import { cva } from "class-variance-authority";

export const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-iris-2/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 active:scale-[0.98]",
  {
    variants: {
      variant: {
        primary:
          "text-white shadow-[0_1px_0_0_rgba(255,255,255,0.15)_inset,0_8px_24px_-8px_rgba(99,102,241,0.6)] bg-[linear-gradient(100deg,var(--iris-1),var(--iris-2)_60%,var(--iris-3))] bg-[length:180%_100%] bg-left hover:bg-right",
        outline:
          "border border-border-strong bg-white/[0.02] text-foreground hover:bg-white/[0.06] hover:border-white/25",
        ghost: "text-foreground/80 hover:text-foreground hover:bg-white/[0.06]",
        subtle: "bg-white/[0.04] text-foreground/90 hover:bg-white/[0.08]",
        destructive:
          "bg-rose-500/10 text-rose-300 ring-1 ring-inset ring-rose-400/30 hover:bg-rose-500/20",
        success:
          "bg-emerald-400/10 text-emerald-300 ring-1 ring-inset ring-emerald-400/30 hover:bg-emerald-400/20",
      },
      size: {
        sm: "h-8 px-3.5 text-xs",
        md: "h-10 px-5 text-sm",
        lg: "h-12 px-7 text-base",
        icon: "h-9 w-9 shrink-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset whitespace-nowrap",
);
