import type { ReactNode } from "react";

interface FieldLabelProps {
    htmlFor: string;
    children: ReactNode;
    /** Mostra o asterisco vermelho de campo obrigatório. */
    required?: boolean;
    className?: string;
}

export function FieldLabel({ htmlFor, children, required = false, className = "mb-1.5" }: FieldLabelProps) {
    return (
        <label htmlFor={htmlFor} className={`block text-xs font-semibold text-neutral-300 ${className}`}>
            {children}
            {required && (
                <span className="ml-0.5 text-danger-400" aria-hidden="true">
                    *
                </span>
            )}
        </label>
    );
}

/** Mensagem de erro de campo, ligada ao input via aria-describedby. */
export function FieldError({ id, children }: { id: string; children: ReactNode }) {
    return (
        <p id={id} className="mt-1.5 text-xs font-medium text-danger-400">
            {children}
        </p>
    );
}
