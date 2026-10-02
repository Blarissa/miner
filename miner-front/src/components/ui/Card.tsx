import type { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    padding?: "sm" | "md";
}

export function Card({ padding = "md", className = "", ...props }: CardProps) {
    const paddingClass = padding === "sm" ? "p-4" : "p-5";
    return <div className={`bg-neutral-800/80 border border-neutral-700/60 rounded-xl ${paddingClass} ${className}`} {...props} />;
}
