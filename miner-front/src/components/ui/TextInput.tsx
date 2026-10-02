import type { InputHTMLAttributes, ReactNode } from "react";

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
    /** Optional leading icon (e.g. a lucide-react icon element). */
    icon?: ReactNode;
    /** Destaca o campo em vermelho (ex.: obrigatório não preenchido). */
    invalid?: boolean;
}

const BASE_INPUT_CLASSES =
    "w-full bg-neutral-900 border rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus-visible:ring-1 transition";

const VALID_CLASSES = "border-neutral-700 focus:border-primary-500 focus-visible:ring-primary-500";
const INVALID_CLASSES = "border-danger-500 bg-danger-500/5 focus:border-danger-500 focus-visible:ring-danger-500";

export function TextInput({ icon, invalid = false, className = "", ...props }: TextInputProps) {
    const stateClasses = invalid ? INVALID_CLASSES : VALID_CLASSES;
    const ariaInvalid = invalid ? true : undefined;

    if (icon) {
        return (
            <div className="relative">
                <span className="absolute left-3 top-2.5 h-4 w-4 text-neutral-400 pointer-events-none [&>svg]:h-4 [&>svg]:w-4">
                    {icon}
                </span>
                <input
                    aria-invalid={ariaInvalid}
                    className={`${BASE_INPUT_CLASSES} ${stateClasses} pl-9 pr-3 ${className}`}
                    {...props}
                />
            </div>
        );
    }

    return <input aria-invalid={ariaInvalid} className={`${BASE_INPUT_CLASSES} ${stateClasses} ${className}`} {...props} />;
}
