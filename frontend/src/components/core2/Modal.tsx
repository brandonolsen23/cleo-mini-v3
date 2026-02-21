import { Dialog, DialogPanel, DialogTitle } from "@headlessui/react";
import Icon from "./Icon";

type ModalProps = {
    className?: string;
    classPanel?: string;
    title?: string;
    isOpen: boolean;
    onClose: () => void;
    children: React.ReactNode;
    isSlidePanel?: boolean;
};

const Modal = ({
    className,
    classPanel,
    title,
    isOpen,
    onClose,
    children,
    isSlidePanel,
}: ModalProps) => (
    <Dialog
        open={isOpen}
        onClose={onClose}
        className={`relative z-50 ${className || ""}`}
    >
        {/* Backdrop */}
        <div
            className="fixed inset-0 bg-black/30 transition-opacity"
            aria-hidden="true"
        />

        {/* Panel container */}
        <div
            className={`fixed inset-0 flex ${
                isSlidePanel
                    ? "items-stretch justify-end"
                    : "items-center justify-center p-4"
            }`}
        >
            <DialogPanel
                className={`${
                    isSlidePanel
                        ? "w-full max-w-md bg-b-surface2 shadow-dropdown overflow-y-auto"
                        : "w-full max-w-lg rounded-3xl bg-b-surface2 shadow-dropdown p-6"
                } ${classPanel || ""}`}
            >
                {title && (
                    <div className="flex items-center justify-between mb-6">
                        <DialogTitle className="text-h6">
                            {title}
                        </DialogTitle>
                        <button
                            className="action"
                            onClick={onClose}
                        >
                            <Icon
                                className="fill-inherit"
                                name="close"
                            />
                        </button>
                    </div>
                )}
                {children}
            </DialogPanel>
        </div>
    </Dialog>
);

export default Modal;
