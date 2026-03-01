import { motion } from "framer-motion";
import { Code2, Eye, Component, Rocket } from "lucide-react";

const features = [
  {
    num: "01",
    icon: Code2,
    title: "AI Code Generation",
    description:
      "Describe what you want in natural language and watch Enter generate production-ready code in seconds. From React components to full-page layouts.",
  },
  {
    num: "02",
    icon: Eye,
    title: "Real-time Preview",
    description:
      "See your changes instantly as they happen. Our split-view interface shows your conversation alongside a live preview of the generated output.",
  },
  {
    num: "03",
    icon: Component,
    title: "Component Library",
    description:
      "Access a rich library of pre-built, customizable components. Mix and match to build complex interfaces faster than ever.",
  },
  {
    num: "04",
    icon: Rocket,
    title: "One-click Deploy",
    description:
      "Deploy your project to production with a single click. Enter handles hosting, CDN, SSL, and continuous deployment automatically.",
  },
];

export default function FeaturesSection() {
  return (
    <section id="features" className="bg-background px-4 py-20 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl text-center">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
        >
          Build Websites & Apps with
          <br />
          Four Powerful <span className="text-foreground">Enter</span> Features
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mt-3 text-muted-foreground"
        >
          The four pillars powering your next-generation products.
        </motion.p>
      </div>

      <div className="mx-auto mt-16 max-w-3xl space-y-12">
        {features.map((feat, idx) => (
          <motion.div
            key={feat.num}
            initial={{ opacity: 0, x: idx % 2 === 0 ? -24 : 24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ duration: 0.5 }}
            className="flex items-start gap-6"
          >
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted">
              <feat.icon className="h-5 w-5 text-foreground" />
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Feature.{feat.num}
              </p>
              <h3 className="mb-2 text-xl font-semibold text-foreground">{feat.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{feat.description}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
