/* Pure layout data for the money-flow view of one case. */

const MIN_WIDTH = 1;
const MAX_WIDTH = 8;

export function flowModel(payments) {
  const nodes = [...new Set(payments.flatMap((p) => [p.from, p.to]))];
  const top = Math.max(...payments.map((p) => Number(p.amount)), 0);
  const links = payments.map((p) => ({
    id: p.id,
    from: p.from,
    to: p.to,
    amount: p.amount,
    width: top > 0 ? Math.max(MIN_WIDTH, (Number(p.amount) / top) * MAX_WIDTH) : MIN_WIDTH,
  }));
  return { nodes, links };
}
