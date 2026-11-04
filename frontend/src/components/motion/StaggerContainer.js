import React from 'react';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: 'spring',
      stiffness: 300,
      damping: 30,
    },
  },
};

export function StaggerContainer({ children, className, style, delay = 0.08 }) {
  const variants = {
    ...containerVariants,
    visible: {
      ...containerVariants.visible,
      transition: {
        ...containerVariants.visible.transition,
        staggerChildren: delay,
      },
    },
  };

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={variants}
      className={className}
      style={style}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className, style }) {
  return (
    <motion.div variants={itemVariants} className={className} style={style}>
      {children}
    </motion.div>
  );
}

export default StaggerContainer;
