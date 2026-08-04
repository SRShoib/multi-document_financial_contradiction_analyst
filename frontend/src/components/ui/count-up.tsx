"use client";

import * as React from "react";
import { useSpring, useMotionValue } from "framer-motion";

export function CountUp({
  value,
  format,
  className,
}: {
  value: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const mv = useMotionValue(0);
  const spring = useSpring(mv, { stiffness: 90, damping: 22, mass: 0.9 });
  const [display, setDisplay] = React.useState(() => (format ? format(0) : "0"));

  React.useEffect(() => {
    mv.set(value);
  }, [value, mv]);

  React.useEffect(() => {
    const unsub = spring.on("change", (v) => {
      setDisplay(format ? format(v) : Math.round(v).toString());
    });
    return unsub;
  }, [spring, format]);

  return <span className={className}>{display}</span>;
}
