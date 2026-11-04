import React from 'react';
import { motion } from 'framer-motion';

const defaultVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export function AnimateIn({ children, delay = 0, className, direction = 'up' }) {
  const directionMap = {
    up: { hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 } },
    down: { hidden: { opacity: 0, y: -20 }, visible: { opacity: 1, y: 0 } },
    left: { hidden: { opacity: 0, x: 30 }, visible: { opacity: 1, x: 0 } },
    right: { hidden: { opacity: 0, x: -30 }, visible: { opacity: 1, x: 0 } },
    fade: { hidden: { opacity: 0 }, visible: { opacity: 1 } },
    scale: { hidden: { opacity: 0, scale: 0.9 }, visible: { opacity: 1, scale: 1 } },
  };

  const variants = directionMap[direction] || defaultVariants;

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={variants}
      transition={{
        type: 'spring',
        stiffness: 300,
        damping: 30,
        delay,
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default AnimateIn;
