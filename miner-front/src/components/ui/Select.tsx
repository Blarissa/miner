import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
    /** Destaca o campo em vermelho (ex.: obrigatório não preenchido). */
    invalid?: boolean;
}

const BASE_SELECT_CLASSES =
    "w-full bg-neutral-900 border rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus-visible:ring-1 transition";

const VALID_CLASSES = "border-neutral-700 focus:border-primary-500 focus-visible:ring-primary-500";
const INVALID_CLASSES = "border-danger-500 bg-danger-500/5 focus:border-danger-500 focus-visible:ring-danger-500";

export function Select({ invalid = false, className = "", children, ...props }: SelectProps) {
    return (
        <select
            aria-invalid={invalid ? true : undefined}
            className={`${BASE_SELECT_CLASSES} ${invalid ? INVALID_CLASSES : VALID_CLASSES} ${className}`}
            {...props}
        >
            {children}
        </select>
    );
}
