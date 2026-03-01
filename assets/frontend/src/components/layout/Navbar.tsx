import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Code2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
const navLinks = [{
  label: "Home",
  href: "/"
}, {
  label: "Templates",
  href: "/#templates"
}, {
  label: "Features",
  href: "/#features"
}, {
  label: "FAQ",
  href: "/#faq"
}];
interface NavbarProps {
  compact?: boolean;
}
export default function Navbar({
  compact
}: NavbarProps) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  return <header className={cn("sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur-lg", compact && "border-b-border")}>
      <nav className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <Code2 className="h-5 w-5 text-foreground" />
          <span className="text-base font-bold tracking-tight text-foreground">Molycure</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-1 md:flex">
          {navLinks.map(link => <Link key={link.href} to={link.href} className={cn("rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground", location.pathname === link.href && "text-foreground")}>
              {link.label}
            </Link>)}
        </div>

        {/* Desktop actions */}
        <div className="hidden items-center gap-2 md:flex">
          <Button variant="outline" size="sm" asChild>
            <Link to="/chat">Start Building</Link>
          </Button>
          <Button size="sm">Sign in</Button>
        </div>

        {/* Mobile hamburger */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon-sm">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-72 bg-background p-6">
            <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
            <div className="flex flex-col gap-4 pt-8">
              {navLinks.map(link => <Link key={link.href} to={link.href} onClick={() => setOpen(false)} className="text-base font-medium text-foreground">
                  {link.label}
                </Link>)}
              <div className="mt-4 flex flex-col gap-2">
                <Button variant="outline" asChild>
                  <Link to="/chat" onClick={() => setOpen(false)}>Start Building</Link>
                </Button>
                <Button>Sign in</Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </nav>
    </header>;
}