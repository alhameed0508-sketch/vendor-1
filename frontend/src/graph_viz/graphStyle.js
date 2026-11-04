/**
 * How the money-flow graph looks: a grey majority with three role hues,
 * each role also told apart by shape so colour is never the only cue.
 * Colours are CSS tokens (App.css) so both themes stay in sync.
 */

const ROLE_STYLE = {
  SOURCE:     { color: 'var(--role-source)',     shape: 'diamond', base: 14, fill: 0.3 },
  AGGREGATOR: { color: 'var(--role-aggregator)', shape: 'hexagon', base: 13, fill: 0.3 },
  MULE:       { color: 'var(--role-mule)',       shape: 'circle',  base: 10, fill: 0.3 },
  LEGITIMATE: { color: 'var(--role-neutral)',    shape: 'circle',  base: 7,  fill: 0.5 },
  UNKNOWN:    { color: 'var(--role-neutral)',    shape: 'circle',  base: 7,  fill: 0.5 },
};

export const LEGEND_ROLES = ['SOURCE', 'AGGREGATOR', 'MULE', 'LEGITIMATE'];

export const roleStyle = role => ROLE_STYLE[role] || ROLE_STYLE.UNKNOWN;

export const nodeRadius = node => roleStyle(node.role).base + (node.smurf_score || 0) * 4;

const clamp01 = value => Math.min(1, Math.max(0, value || 0));

/** Risk is one ink colour; the ring gets heavier as the score rises. */
export const ringWidth = score => 0.75 + 2.75 * clamp01(score);

const polygon = points => `M${points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('L')}Z`;

export function shapePath(shape, r) {
  if (shape === 'diamond') {
    const d = r * 1.2;
    return polygon([[0, -d], [d, 0], [0, d], [-d, 0]]);
  }
  if (shape === 'hexagon') {
    return polygon([0, 1, 2, 3, 4, 5].map(i => {
      const angle = (Math.PI / 3) * i - Math.PI / 2;
      return [r * 1.08 * Math.cos(angle), r * 1.08 * Math.sin(angle)];
    }));
  }
  return `M${-r},0A${r},${r} 0 1,0 ${r},0A${r},${r} 0 1,0 ${-r},0Z`;
}

const FLAGGED_EDGE = { stroke: 'var(--text-secondary)', opacity: 0.8, dash: null };
const OTHER_EDGE = { stroke: 'var(--text-faint)', opacity: 0.45, dash: '4 4' };

export const edgeStyle = flagged => (flagged ? FLAGGED_EDGE : OTHER_EDGE);
