import * as React from "react";
import { TextArea as RadixTextArea } from "@radix-ui/themes";

import { cn } from "@/lib/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, color: _color, ...props }, ref) => {
    return (
      <RadixTextArea
        size="2"
        variant="surface"
        className={cn(className)}
        ref={ref}
        {...(props as any)}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export { Textarea };
