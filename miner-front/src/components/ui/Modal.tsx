import { useEffect, useRef, type ReactNode } from "react";

interface ModalProps {
    open: boolean;
    onClose: () => void;
    /** Id applied to the title element and referenced by aria-labelledby. */
    titleId: string;
    title: ReactNode;
    children: ReactNode;
    footer?: ReactNode;
    maxWidthClassName?: string;
}

/**
 * Generic dialog wrapper: role="dialog", aria-modal, Escape-to-close,
 * backdrop-click-to-close (clicks inside the panel do not bubble to the
 * backdrop), and focus return to whatever element was focused before the
 * modal opened (normally the button that triggered it).
 */
export function Modal({
    open,
    onClose,
    titleId,
    title,
    children,
    footer,
    maxWidthClassName = "max-w-3xl",
}: ModalProps) {
    const previouslyFocused = useRef<HTMLElement | null>(null);
    const dialogRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!open) return;

        previouslyFocused.current = document.activeElement as HTMLElement | null;
        dialogRef.current?.focus();

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.stopPropagation();
                onClose();
            }
        };
        document.addEventListener("keydown", handleKeyDown);

        return () => {
            document.removeEventListener("keydown", handleKeyDown);
            previouslyFocused.current?.focus?.();
        };
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
            onClick={onClose}
        >
            <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                tabIndex={-1}
                onClick={(event) => event.stopPropagation()}
                className={`bg-neutral-900 border border-neutral-700 rounded-xl w-full ${maxWidthClassName} max-h-[85vh] flex flex-col shadow-2xl focus:outline-none`}
            >
                <div className="p-4 border-b border-neutral-800 flex items-center justify-between bg-neutral-950/60 rounded-t-xl">
                    <div id={titleId} className="flex items-center gap-2 font-semibold text-sm text-neutral-100">
                        {title}
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Fechar"
                        className="text-neutral-400 hover:text-white text-xs px-2.5 py-1 rounded bg-neutral-800 border border-neutral-700 hover:bg-neutral-700 transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
                    >
                        Fechar
                    </button>
                </div>
                <div className="p-4 overflow-y-auto flex-1 space-y-5">
                    {children}
                </div>
                {footer}
            </div>
        </div>
    );
}
