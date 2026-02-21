import * as React from "react";
import {
  CloseButton,
  Dialog,
  DialogPanel,
  DialogTitle,
  Description,
  Transition,
  TransitionChild,
} from "@headlessui/react";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

/* ---- Root ---- */
interface SheetProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

function Sheet({ open = false, onOpenChange, children }: SheetProps) {
  return (
    <Transition show={open}>
      <Dialog onClose={() => onOpenChange?.(false)} className="relative z-50">
        {children}
      </Dialog>
    </Transition>
  );
}

/* ---- Overlay ---- */
const SheetOverlay = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <TransitionChild
    as={React.Fragment}
    enter="ease-out duration-300"
    enterFrom="opacity-0"
    enterTo="opacity-100"
    leave="ease-in duration-200"
    leaveFrom="opacity-100"
    leaveTo="opacity-0"
  >
    <div
      ref={ref}
      className={cn("fixed inset-0 bg-black/80", className)}
      {...props}
    />
  </TransitionChild>
));
SheetOverlay.displayName = "SheetOverlay";

/* ---- Content (slide panel) ---- */
const sheetVariants = cva(
  "fixed z-50 gap-4 bg-background p-6 shadow-lg",
  {
    variants: {
      side: {
        top: "inset-x-0 top-0 border-b",
        bottom: "inset-x-0 bottom-0 border-t",
        left: "inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm",
        right: "inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm",
      },
    },
    defaultVariants: {
      side: "right",
    },
  }
);

const slideTransition: Record<string, { enter: string; leave: string }> = {
  top: { enter: "translate-y-0", leave: "-translate-y-full" },
  bottom: { enter: "translate-y-0", leave: "translate-y-full" },
  left: { enter: "translate-x-0", leave: "-translate-x-full" },
  right: { enter: "translate-x-0", leave: "translate-x-full" },
};

interface SheetContentProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof sheetVariants> {}

const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ side = "right", className, children, ...props }, ref) => {
    const slide = slideTransition[side ?? "right"];
    return (
      <>
        <SheetOverlay />
        <TransitionChild
          as={React.Fragment}
          enter="transform transition ease-in-out duration-500"
          enterFrom={slide.leave}
          enterTo={slide.enter}
          leave="transform transition ease-in-out duration-300"
          leaveFrom={slide.enter}
          leaveTo={slide.leave}
        >
          <DialogPanel
            ref={ref}
            className={cn(sheetVariants({ side }), className)}
            {...props}
          >
            {children}
            <CloseButton className="absolute right-4 top-4 opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </CloseButton>
          </DialogPanel>
        </TransitionChild>
      </>
    );
  }
);
SheetContent.displayName = "SheetContent";

/* ---- Subcomponents ---- */
const SheetHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-2 text-center sm:text-left",
      className
    )}
    {...props}
  />
);
SheetHeader.displayName = "SheetHeader";

const SheetFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      className
    )}
    {...props}
  />
);
SheetFooter.displayName = "SheetFooter";

const SheetTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <DialogTitle
    ref={ref}
    className={cn("text-lg font-semibold text-foreground", className)}
    {...props}
  />
));
SheetTitle.displayName = "SheetTitle";

const SheetDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
SheetDescription.displayName = "SheetDescription";

export {
  Sheet,
  SheetOverlay,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
};
