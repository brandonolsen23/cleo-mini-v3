import * as React from "react";
import {
  Popover as HeadlessPopover,
  PopoverButton,
  PopoverPanel,
  Transition,
} from "@headlessui/react";

import { cn } from "@/lib/utils";

/* ---- Root ---- */
interface PopoverProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

function Popover({ children }: PopoverProps) {
  return <HeadlessPopover className="relative">{children}</HeadlessPopover>;
}

/* ---- Trigger ---- */
interface PopoverTriggerProps {
  asChild?: boolean;
  children: React.ReactNode;
}

function PopoverTrigger({ children }: PopoverTriggerProps) {
  return <PopoverButton as={React.Fragment}>{children}</PopoverButton>;
}

/* ---- Content ---- */
interface PopoverContentProps extends React.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end";
  sideOffset?: number;
}

const PopoverContent = React.forwardRef<HTMLDivElement, PopoverContentProps>(
  ({ className, children, ...props }, ref) => (
    <Transition
      enter="transition ease-out duration-100"
      enterFrom="opacity-0 scale-95"
      enterTo="opacity-100 scale-100"
      leave="transition ease-in duration-75"
      leaveFrom="opacity-100 scale-100"
      leaveTo="opacity-0 scale-95"
    >
      <PopoverPanel
        ref={ref}
        anchor="bottom start"
        className={cn(
          "z-50 mt-1 w-72 rounded-xl border border-border bg-popover p-4 text-popover-foreground shadow-dropdown outline-none",
          className
        )}
        {...props}
      >
        {children}
      </PopoverPanel>
    </Transition>
  )
);
PopoverContent.displayName = "PopoverContent";

export { Popover, PopoverTrigger, PopoverContent };
