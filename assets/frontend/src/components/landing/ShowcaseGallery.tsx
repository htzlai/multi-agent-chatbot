import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

interface ShowcaseItem {
  label: string;
  gradient: string;
  span?: string;
}

const items: ShowcaseItem[] = [
  { label: "Restaurant Landing", gradient: "from-rose-200 to-orange-200", span: "col-span-1" },
  { label: "Sneaker Store", gradient: "from-emerald-200 to-teal-200", span: "col-span-1" },
  { label: "Tech Review", gradient: "from-violet-200 to-purple-200", span: "col-span-1" },
  { label: "Startup SaaS", gradient: "from-blue-200 to-cyan-200", span: "col-span-1" },
  { label: "Portfolio Site", gradient: "from-amber-200 to-yellow-200", span: "md:col-span-2" },
  { label: "Knowledge Base", gradient: "from-pink-200 to-fuchsia-200", span: "col-span-1" },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function ShowcaseGallery() {
  return (
    <section className="bg-background px-4 py-16 sm:px-6 lg:px-8">
      <motion.div
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.15 }}
        className="mx-auto grid max-w-6xl grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4"
      >
        {items.map((item) => (
          <motion.div
            key={item.label}
            variants={itemVariants}
            className={`group relative cursor-pointer overflow-hidden rounded-xl ${item.span ?? ""}`}
          >
            <div
              className={`aspect-[4/3] w-full bg-gradient-to-br ${item.gradient} transition-transform duration-300 group-hover:scale-[1.03]`}
            />
            <Badge
              variant="secondary"
              className="absolute left-3 top-3 bg-background/80 text-foreground backdrop-blur-sm"
            >
              {item.label}
            </Badge>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
