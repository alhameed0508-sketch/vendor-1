import React from 'react';
import { accountRows, formatAmount, roleLabel } from './graphModel';
import { roleStyle, shapePath } from './graphStyle';

function RoleMark({ role }) {
  const { color, shape, fill } = roleStyle(role);
  return (
    <svg width={14} height={14} viewBox="-7 -7 14 14" aria-hidden="true">
      <path d={shapePath(shape, 5)} fill={color} fillOpacity={fill} stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

/** Table view of the same graph: readable without colour, sortable by eye, works on phones. */
export default function AccountList({ nodes, edges, onSelect }) {
  return (
    <div className="account-list">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Account</th>
            <th scope="col">Role</th>
            <th scope="col" className="num">Risk</th>
            <th scope="col" className="num">Sent</th>
            <th scope="col" className="num">Received</th>
          </tr>
        </thead>
        <tbody>
          {accountRows(nodes, edges).map(({ node, sent, received }) => (
            <tr key={node.account_id}>
              <td>
                <button type="button" className="account-list-id" onClick={() => onSelect(node)}>
                  {node.account_id}
                </button>
              </td>
              <td><span className="account-list-role"><RoleMark role={node.role} />{roleLabel(node.role)}</span></td>
              <td className="num">{Math.round((node.smurf_score || 0) * 100)}%</td>
              <td className="num">{formatAmount(sent)}</td>
              <td className="num">{formatAmount(received)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
