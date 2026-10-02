import type { InputHTMLAttributes, ReactNode } from "react";

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
    label: ReactNode;
    /** Overrides the wrapping <label> classes, for the few spots whose layout differs. */
    labelClassName?: string;
}

const DEFAULT_LABEL_CLASSES = "flex items-center gap-2 cursor-pointer text-sm text-neutral-300 font-medium";

export function Checkbox({
    label,
    labelClassName = DEFAULT_LABEL_CLASSES,
    className = "",
    id,
    ...props
}: CheckboxProps) {
    return (
        <label htmlFor={id} className={labelClassName}>
            <input
                type="checkbox"
                id={id}
                className={`rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500 focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-neutral-900 disabled:opacity-50 ${className}`}
                {...props}
            />
            {label}
        </label>
    );
}
