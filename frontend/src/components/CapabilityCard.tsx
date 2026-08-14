import { Link } from "react-router-dom";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { Card } from "@/components/Card";
import { IconBadge, type IconTone } from "@/components/IconBadge";

interface CapabilityCardProps {
  icon: LucideIcon;
  tone: IconTone;
  title: string;
  description: string;
  /** Real in-app route — every capability links somewhere that actually exists,
   * even if that destination is currently a NotYetBuilt placeholder naming its phase. */
  to: string;
}

export function CapabilityCard({ icon, tone, title, description, to }: CapabilityCardProps) {
  return (
    <Link to={to} className="group block">
      <Card className="h-full p-5 transition-shadow hover:shadow-md">
        <IconBadge icon={icon} tone={tone} />
        <h3 className="mt-3 text-sm font-semibold text-navy">{title}</h3>
        <p className="mt-1 text-sm text-muted-text">{description}</p>
        <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary-blue">
          Learn more
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </span>
      </Card>
    </Link>
  );
}
