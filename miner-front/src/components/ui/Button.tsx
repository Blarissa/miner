import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "cta" | "secondary" | "danger";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
    primary: "bg-primary-700 hover:bg-primary-600 text-white shadow-md",
    /** Ação principal da tela (mesmo laranja do botão da landing). */
    cta: "bg-orange-500 hover:bg-orange-400 text-slate-900 shadow-md",
    secondary: "bg-neutral-800 hover:bg-neutral-700 text-neutral-100 border border-neutral-700",
    danger: "bg-danger-600 hover:bg-danger-500 text-white border border-danger-500",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
}

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
    return (
        <button
            type={type}
            className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-900 ${VARIANT_CLASSES[variant]} ${className}`}
            {...props}
        />
    );
}
