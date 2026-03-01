import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";

export default function CTASection() {
  return (
    <section className="bg-background px-4 py-24 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="mx-auto max-w-2xl text-center"
      >
        <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-5xl">
          Press <span className="text-foreground">Enter</span>
          <br />
          Build Your Apps
        </h2>
        <p className="mx-auto mt-4 max-w-md text-muted-foreground">
          Your AI Dev Agent for the Vibe Coding Era.
          <br />
          Orchestrate code, cloud, and collaboration to ship real products
        </p>
        <Button size="xl" className="mt-8 rounded-full" asChild>
          <Link to="/chat">Get Started Free</Link>
        </Button>
      </motion.div>
    </section>
  );
}
