import React, { useEffect, useRef } from 'react';
import { useSpring, useTransform, motion, useInView } from 'framer-motion';

export default function AnimatedCounter({
  end,
  prefix = '',
  suffix = '',
  decimals = 0,
  duration = 1.2,
  style = {},
  className = '',
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  const numEnd = typeof end === 'number' ? end : parseFloat(String(end).replace(/[^0-9.-]/g, ''));
  const isValidNumber = !isNaN(numEnd);

  const springValue = useSpring(0, {
    stiffness: 100,
    damping: 30,
    duration: duration * 1000,
  });

  const displayValue = useTransform(springValue, (latest) => {
    if (!isValidNumber) return `${prefix}${end}${suffix}`;
    if (decimals > 0) {
      return `${prefix}${latest.toFixed(decimals)}${suffix}`;
    }
    return `${prefix}${Math.round(latest).toLocaleString('en-IN')}${suffix}`;
  });

  useEffect(() => {
    if (isInView && isValidNumber) {
      springValue.set(numEnd);
    }
  }, [isInView, numEnd, isValidNumber, springValue]);

  if (!isValidNumber) {
    return (
      <span ref={ref} style={style} className={className}>
        {prefix}{end}{suffix}
      </span>
    );
  }

  return (
    <motion.span ref={ref} style={style} className={className}>
      {displayValue}
    </motion.span>
  );
}
