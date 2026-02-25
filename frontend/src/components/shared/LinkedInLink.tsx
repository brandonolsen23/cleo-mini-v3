import { LinkedinLogo } from "@phosphor-icons/react";

interface LinkedInLinkProps {
  name: string;
  size?: number;
}

export default function LinkedInLink({ name, size = 14 }: LinkedInLinkProps) {
  const url = `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(name)}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title="Search LinkedIn"
      className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors shrink-0"
      onClick={(e) => e.stopPropagation()}
    >
      <LinkedinLogo size={size} />
    </a>
  );
}
