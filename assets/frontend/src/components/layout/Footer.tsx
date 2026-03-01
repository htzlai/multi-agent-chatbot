import { Link } from "react-router-dom";
import { Code2, ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const resources = [
  { label: "Templates", href: "/#templates" },
  { label: "Features", href: "/#features" },
  { label: "FAQ", href: "/#faq" },
  { label: "Blog", href: "#" },
  { label: "Changelog", href: "#" },
];

const terms = [
  { label: "Terms of Service", href: "#" },
  { label: "Privacy Policy", href: "#" },
];

const contact = [
  { label: "Feedback", href: "#" },
  { label: "Support", href: "#" },
];

export default function Footer() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <Link to="/" className="flex items-center gap-2">
              <Code2 className="h-5 w-5 text-foreground" />
              <span className="text-base font-bold text-foreground">Enter</span>
            </Link>
          </div>

          {/* Resources */}
          <div>
            <h4 className="mb-3 text-sm font-semibold text-foreground">Resources</h4>
            <ul className="space-y-2">
              {resources.map((link) => (
                <li key={link.label}>
                  <Link
                    to={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Terms */}
          <div>
            <h4 className="mb-3 text-sm font-semibold text-foreground">Terms</h4>
            <ul className="space-y-2">
              {terms.map((link) => (
                <li key={link.label}>
                  <Link
                    to={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h4 className="mb-3 text-sm font-semibold text-foreground">Contact</h4>
            <ul className="space-y-2">
              {contact.map((link) => (
                <li key={link.label}>
                  <Link
                    to={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <Separator className="my-8" />

        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} Enter. All rights reserved.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-xs text-muted-foreground"
            onClick={scrollToTop}
          >
            Back to top
            <ArrowUp className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </footer>
  );
}
