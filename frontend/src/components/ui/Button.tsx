import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand/90 disabled:bg-brand/40",
  secondary:
    "border border-border bg-surface text-foreground hover:bg-surface-2 disabled:opacity-50",
  danger: "bg-danger text-white hover:bg-danger/90 disabled:bg-danger/40",
  ghost: "text-foreground/70 hover:bg-surface-2 hover:text-foreground disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  sm: "px-2.5 py-1 text-xs",
  md: "px-4 py-2 text-sm",
};

/** Bouton d'action avec 4 variantes (primaire, secondaire, danger, discret). */
export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    />
  );
}
